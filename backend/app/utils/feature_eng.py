"""
Feature engineering module.
Transforms raw checkout request data into model-ready features.
"""

import re
from typing import TypedDict

class ModelFeatures(TypedDict):
    category: str
    cart_value: float
    order_quantity: int
    payment_method: str
    pincode: str
    user_age: int
    user_gender: str
    discount_pct: float
    shipping_method: str
    address_length: int
    has_vague_terms: int
    pincode_rto_rate: float
    ip_velocity_15m: int
    ip_velocity_60m: int
    device_velocity_15m: int

# Vague address patterns common in Indian RTO fraud
VAGUE_PATTERN = re.compile(
    r"\b(near|opp|opposite|behind|beside|nr|next to|village|chowk|"
    r"bus stand|railway|station|masjid|temple|mandir|church|mosque|"
    r"petrol pump|hospital|school|market|bazaar|main road)\b",
    re.IGNORECASE,
)


def extract_features(
    shipping_address: str,
    pincode: str,
    cart_value: float,
    category: str,
    payment_method: str,
    order_quantity: int,
    user_age: int,
    user_gender: str,
    discount_pct: float,
    shipping_method: str,
    pincode_rto_rate: float,
    ip_velocity_15m: int = 0,
    ip_velocity_60m: int = 0,
    device_velocity_15m: int = 0,
) -> ModelFeatures:
    """
    Build feature dict matching the model's expected input.

    Returns:
        ModelFeatures with keys matching FEATURE_COLS from training
    """
    # Address length (key risk signal)
    address_length = len(shipping_address.strip())

    # Vague terms detection
    has_vague = 1 if VAGUE_PATTERN.search(shipping_address) else 0

    features: ModelFeatures = {
        "category": category,
        "cart_value": cart_value,
        "order_quantity": order_quantity,
        "payment_method": payment_method,
        "pincode": str(pincode),
        "user_age": user_age,
        "user_gender": user_gender,
        "discount_pct": discount_pct,
        "shipping_method": shipping_method,
        "address_length": address_length,
        "has_vague_terms": has_vague,
        "pincode_rto_rate": pincode_rto_rate,
        # ── Velocity features (live from Redis at inference time) ──
        "ip_velocity_15m":     min(ip_velocity_15m,  100),  # cap matches training clip
        "ip_velocity_60m":     min(ip_velocity_60m,  100),
        "device_velocity_15m": min(device_velocity_15m, 100),
    }

    return features



# Human-readable risk factor labels for the dashboard
RISK_FACTOR_LABELS = {
    "address_length": "Address too short / incomplete",
    "has_vague_terms": "Vague address terms detected (e.g., 'near', 'opp')",
    "pincode_rto_rate": "High-RTO pincode area",
    "payment_method": "Cash on Delivery payment",
    "cart_value": "Cart value risk signal",
    "pincode": "Pincode-level risk",
    "user_age": "User age risk pattern",
    "discount_pct": "High discount usage",
    "order_quantity": "Order quantity anomaly",
    "category": "Product category risk",
    "shipping_method": "Shipping method risk",
    "user_gender": "Demographic risk pattern",
    "ip_velocity_15m": "High IP activity (last 15 min)",
    "ip_velocity_60m": "High IP activity (last 60 min)",
    "device_velocity_15m": "Suspicious device activity (last 15 min)",
}


def get_risk_label(feature_name: str) -> str:
    """Get human-readable label for a risk factor."""
    return RISK_FACTOR_LABELS.get(feature_name, feature_name)
