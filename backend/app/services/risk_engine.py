"""
Risk Engine — the core orchestrator.
Combines feature extraction, velocity checks, ML inference, and SHAP explainability.
Also maintains the in-memory audit log for the merchant dashboard.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
import re
import httpx
from starlette.concurrency import run_in_threadpool

from ..models.ml_model import rto_model
from ..models.schemas import (
    RiskEvaluationRequest,
    RiskEvaluationResponse,
    CheckoutUIRules,
    AuditTrail,
    AuditLogEntry,
    FailureLogEntry,
    DashboardMetrics,
)
from ..utils.feature_eng import extract_features, get_risk_label
from ..services.velocity import velocity_service
from ..config import settings


# ── In-memory audit stores (sufficient for hackathon demo) ───────────────────
_audit_log: list[AuditLogEntry] = []
_failure_log: list[FailureLogEntry] = []
_total_evaluations = 0
_total_cod_blocked = 0
_total_margin_saved = 0.0
_risk_score_sum = 0.0


async def verify_pincode_location(pincode: str, city: str, state: str) -> tuple[float, list[str]]:
    risk_bump = 0.0
    factors = []
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"https://api.postalpincode.in/pincode/{pincode}")
            if resp.status_code == 200:
                data = resp.json()
                if data and data[0].get("Status") == "Success":
                    post_offices = data[0].get("PostOffice", [])
                    if post_offices:
                        actual_state = post_offices[0].get("State", "").lower()
                        actual_district = post_offices[0].get("District", "").lower()
                        
                        user_state = state.lower()
                        user_city = city.lower()
                        
                        state_mismatch = user_state not in actual_state and actual_state not in user_state
                        city_mismatch = user_city not in actual_district and actual_district not in user_city
                        
                        if state_mismatch or city_mismatch:
                            risk_bump += 0.40
                            factors.append("state_or_district_mismatch (Rule)")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Pincode API failed: {e}")
        
    return risk_bump, factors


def get_current_threshold() -> float:
    """Get the current risk threshold."""
    return settings.RISK_THRESHOLD


def set_threshold(new_threshold: float):
    """Update the risk threshold dynamically."""
    settings.RISK_THRESHOLD = new_threshold


def calculate_composite_risk(ml_prob: float, address: str) -> tuple[float, list[str]]:
    risk_factors = []
    
    clean_addr = address.strip().lower()
    char_len = len(clean_addr)
    word_count = len(clean_addr.split())
    
    # 1. Address Length & Word Count Check
    is_critically_short = char_len < 18 or word_count < 3
    
    # 2. Check for missing building/house numbers (no digits)
    has_no_digits = not any(char.isdigit() for char in clean_addr)
    
    # 3. Check for vague filler phrases (only penalize if there are no specific building numbers)
    vague_phrases = ["near", "opposite", "opp", "behind", "main road", "bus stand"]
    has_vague_terms = any(phrase in clean_addr for phrase in vague_phrases) and word_count <= 8 and has_no_digits

    adjusted_risk = ml_prob

    if is_critically_short:
        # Boost risk score or enforce a minimum risk floor (e.g. 0.75)
        adjusted_risk = max(adjusted_risk, 0.78)
        risk_factors.append("critically_short_address (Rule)")

    if has_no_digits and is_critically_short:
        adjusted_risk = max(adjusted_risk, 0.82)
        risk_factors.append("missing_house_or_flat_number (Rule)")

    if has_vague_terms:
        adjusted_risk = max(adjusted_risk, 0.80)
        risk_factors.append("vague_landmark_without_specifics (Rule)")

    return min(adjusted_risk, 1.0), risk_factors

MAX_RETAIL_QUANTITY = 5
MAX_ALLOWED_COD_AMOUNT = 8000  # Strict cap on COD orders (e.g., ₹8,000)

def evaluate_quantity_and_value_risk(quantity: int, cart_value: float, category: str) -> tuple[float, list[str]]:
    risk_bump = 0.0
    factors = []

    # 1. Abnormal Quantity Threshold
    if quantity >= MAX_RETAIL_QUANTITY and category.lower() == "electronics":
        risk_bump += 0.80  # Push to high risk
        factors.append("bulk_retail_quantity_anomaly (Rule)")

    # 2. High-Ticket Cart Ceiling for COD
    if cart_value > MAX_ALLOWED_COD_AMOUNT:
        risk_bump += 1.0  # Absolutely block COD
        factors.append("high_ticket_value_exceeds_cod_cap (Rule)")

    return risk_bump, factors

def evaluate_address_robustness(address: str) -> tuple[float, list[str]]:
    clean_addr = address.strip().lower()
    factors = []
    risk_penalty = 0.0
    
    # 1. Unique Word Check (Defeats copy-paste padding)
    words = clean_addr.split()
    unique_words = len(set(words))
    
    if unique_words < 3:
        risk_penalty += 0.30
        factors.append("low_unique_word_count (Rule)")
        
    # 2. Repeated Character Spam (Defeats "aaaaaaa" padding)
    # Regex looks for the same character repeating 5 or more times
    if re.search(r'(.)\1{4,}', clean_addr):
        risk_penalty += 0.40
        factors.append("adversarial_character_padding (Rule)")
        
    return risk_penalty, factors


async def evaluate_risk(request: RiskEvaluationRequest) -> RiskEvaluationResponse:
    """
    Full risk evaluation pipeline:
    1. Fetch velocity counters from Redis
    2. Extract features
    3. Run ML inference
    4. Get SHAP explanations
    5. Build response with UI rules
    6. Log to audit trail
    """
    global _total_evaluations, _total_cod_blocked, _total_margin_saved, _risk_score_sum

    _total_evaluations += 1
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    # ── 1. Velocity checks (Redis) ───────────────────────────────
    try:
        ip_vel_15 = await velocity_service.get_ip_velocity(request.customer_ip, 15)
        ip_vel_60 = await velocity_service.get_ip_velocity(request.customer_ip, 60)
        dev_vel_15 = await velocity_service.get_device_velocity(request.device_hash, 15)
        pincode_vel_15 = await velocity_service.get_pincode_velocity(request.pincode, 15)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Velocity checks failed, falling back to 0: {e}")
        ip_vel_15 = ip_vel_60 = dev_vel_15 = pincode_vel_15 = 0

    # ── 2. Get pincode risk rate ─────────────────────────────────
    pincode_rto_rate = rto_model.get_pincode_risk_rate(request.pincode)

    # ── 3. Extract features ──────────────────────────────────────
    features = extract_features(
        shipping_address=request.shipping_address,
        pincode=request.pincode,
        cart_value=request.cart_value,
        category=request.category or "Fashion",
        payment_method=request.payment_method or "COD",
        order_quantity=request.order_quantity or 1,
        user_age=request.user_age or 30,
        user_gender=request.user_gender or "Male",
        discount_pct=request.discount_pct or 0.0,
        shipping_method=request.shipping_method or "Standard (5-7 days)",
        pincode_rto_rate=pincode_rto_rate,
        ip_velocity_15m=ip_vel_15,
        ip_velocity_60m=ip_vel_60,
        device_velocity_15m=dev_vel_15,
    )

    # ── 4. ML Inference (Offloaded to threadpool to prevent blocking) ──
    rto_prob, shap_values = await run_in_threadpool(rto_model.predict, features)

    # ── 5. SHAP explanation ──────────────────────────────────────
    top_factors = await run_in_threadpool(rto_model.get_top_risk_factors, shap_values, 3)
    
    filtered_factors = []
    for f in top_factors:
        if f['feature'] == 'order_quantity' and (request.order_quantity or 1) < 5:
            continue
        filtered_factors.append(f)
        
    factor_labels = [f"{get_risk_label(f['feature'])} (SHAP: +{f['impact']:.2f})" for f in filtered_factors]

    # Add velocity-based risk factors to the explanation if significant
    # Note: the model now natively scores these features — we only ADD them
    # to the *explanation text* here, not modify the probability score.
    if ip_vel_15 > 3:
        factor_labels.append(f"High IP velocity: {ip_vel_15} requests in 15 min (Heuristic)")
    if dev_vel_15 > 3:
        factor_labels.append(f"Suspicious device: {dev_vel_15} requests in 15 min (Heuristic)")

    # Apply Address Risk Floor / Rule Booster
    rto_prob, address_factors = calculate_composite_risk(rto_prob, request.shipping_address)
    factor_labels.extend(address_factors)
    
    # Apply Address Robustness (Unique Words & Character Padding)
    robustness_penalty, robustness_factors = evaluate_address_robustness(request.shipping_address)
    rto_prob = min(rto_prob + robustness_penalty, 1.0)
    factor_labels.extend(robustness_factors)

    # Apply City/State Mismatch Guardrail
    if request.city and request.state:
        mismatch_penalty, mismatch_factors = await verify_pincode_location(request.pincode, request.city, request.state)
        rto_prob = min(rto_prob + mismatch_penalty, 1.0)
        factor_labels.extend(mismatch_factors)
    
    # Apply Proxy Defense Guardrail
    if pincode_vel_15 > 15:
        rto_prob = max(rto_prob, 0.95)
        factor_labels.append("distributed_proxy_attack_detected (Rule)")

    # Apply Bulk & High-Ticket Risk Guardrails
    risk_bump, cart_factors = evaluate_quantity_and_value_risk(
        quantity=request.order_quantity or 1,
        cart_value=request.cart_value,
        category=request.category or "Fashion"
    )
    rto_prob = min(rto_prob + risk_bump, 1.0)
    factor_labels.extend(cart_factors)

    # ── 6. Classify risk ─────────────────────────────────────────
    threshold = settings.RISK_THRESHOLD
    if rto_prob >= threshold:
        category = "HIGH"
        cod_supported = False
        discount_active = True
        
        # Max discount leaves at least 1 INR for Razorpay minimum order limit
        calculated_discount = int(request.cart_value * 0.05 * 100)
        max_allowed_discount = int((request.cart_value - 1) * 100)
        discount_paise = max(0, min(calculated_discount, max_allowed_discount))
        
        discount_inr = discount_paise / 100.0
        message = (
            f"COD is unavailable for this location. "
            f"Pay via UPI for an instant Rs.{discount_inr:.0f} discount."
        )
        action = "COD_BLOCKED"
        _total_cod_blocked += 1
        _total_margin_saved += request.cart_value * 0.12  # ~12% logistics margin saved
    elif rto_prob >= threshold * 0.6:
        category = "MEDIUM"
        cod_supported = True
        discount_active = True
        
        calculated_discount = int(request.cart_value * 0.03 * 100)
        max_allowed_discount = int((request.cart_value - 1) * 100)
        discount_paise = max(0, min(calculated_discount, max_allowed_discount))
        
        discount_inr = discount_paise / 100.0
        message = f"Get Rs.{discount_inr:.0f} off by paying via UPI!"
        action = "COD_ALLOWED"
    else:
        category = "LOW"
        cod_supported = True
        discount_active = False
        discount_paise = 0
        message = None
        action = "COD_ALLOWED"

    _risk_score_sum += rto_prob

    # ── 7. Build response ────────────────────────────────────────
    response = RiskEvaluationResponse(
        risk_score=round(rto_prob, 4),
        rto_probability_category=category,
        checkout_ui_rules=CheckoutUIRules(
            cod_supported=cod_supported,
            discount_incentive_active=discount_active,
            discount_amount_in_paise=discount_paise,
            display_message=message,
        ),
        audit_trail=AuditTrail(top_risk_factors=factor_labels),
    )

    # ── 8. Persist audit entry ───────────────────────────────────
    audit_entry = AuditLogEntry(
        order_id=order_id,
        timestamp=now,
        risk_score=round(rto_prob, 4),
        rto_category=category,
        action_taken=action,
        top_risk_factors=factor_labels,
        cart_value=request.cart_value,
        pincode=request.pincode,
        shipping_address=request.shipping_address,
    )
    _audit_log.append(audit_entry)

    # Keep only last 1000 entries in memory
    if len(_audit_log) > 1000:
        _audit_log.pop(0)

    return response


def log_failure(error_type: str, error_message: str, fallback_action: str = "COD_ALLOWED_DEFAULT"):
    """Log a failure/degradation event."""
    entry = FailureLogEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        error_type=error_type,
        error_message=error_message,
        fallback_action=fallback_action,
    )
    _failure_log.append(entry)
    if len(_failure_log) > 500:
        _failure_log.pop(0)


def get_dashboard_metrics() -> DashboardMetrics:
    """Get aggregated metrics for the merchant dashboard."""
    return DashboardMetrics(
        total_evaluations=_total_evaluations,
        rto_prevented=_total_cod_blocked,
        cod_blocked=_total_cod_blocked,
        total_false_positives_estimate=int(_total_cod_blocked * 0.35),  # ~35% FP rate from model eval
        net_margin_saved_inr=round(_total_margin_saved, 2),
        avg_risk_score=round(_risk_score_sum / max(_total_evaluations, 1), 4),
        current_threshold=settings.RISK_THRESHOLD,
    )


def get_audit_log(limit: int = 50, offset: int = 0) -> list[AuditLogEntry]:
    """Get paginated audit log entries (newest first)."""
    reversed_log = list(reversed(_audit_log))
    return reversed_log[offset:offset + limit]


def get_failure_log() -> list[FailureLogEntry]:
    """Get all failure/degradation events."""
    return list(reversed(_failure_log))
