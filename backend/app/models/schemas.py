"""
Pydantic request/response schemas for all API endpoints.
Strict validation to ensure zero malformed requests reach the ML model.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# Request Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class RiskEvaluationRequest(BaseModel):
    """POST /api/v1/evaluate-risk request body."""
    cart_value: float = Field(..., gt=0, description="Cart value in INR")
    shipping_address: str = Field(..., min_length=1, max_length=500, description="Shipping address string")
    pincode: str = Field(..., description="6-digit Indian pincode")
    customer_ip: str = Field(..., description="Customer IP address")
    device_hash: str = Field(..., min_length=1, max_length=64, description="Device fingerprint hash")
    timestamp: Optional[str] = Field(default=None, description="ISO 8601 timestamp")

    # Optional fields that improve prediction if available
    category: Optional[str] = Field(default="Fashion", description="Product category")
    order_quantity: Optional[int] = Field(default=1, ge=1, description="Order quantity")
    payment_method: Optional[str] = Field(default="COD", description="Payment method")
    user_age: Optional[int] = Field(default=30, ge=18, le=100, description="User age")
    user_gender: Optional[str] = Field(default="Male", description="User gender")
    discount_pct: Optional[float] = Field(default=0.0, ge=0, le=100, description="Discount percentage")
    shipping_method: Optional[str] = Field(default="Standard (5-7 days)", description="Shipping method")
    city: Optional[str] = Field(default=None, description="City")
    state: Optional[str] = Field(default=None, description="State")

    @field_validator("pincode")
    @classmethod
    def validate_pincode(cls, v):
        v = v.strip()
        if not v.isdigit() or len(v) != 6:
            raise ValueError("Pincode must be exactly 6 digits")
        if v[0] == "0":
            raise ValueError("Indian pincodes do not start with 0")
        return v

    @field_validator("customer_ip")
    @classmethod
    def validate_ip(cls, v):
        parts = v.strip().split(".")
        if len(parts) != 4:
            raise ValueError("Invalid IP address format")
        return v.strip()


class CreateOrderRequest(BaseModel):
    """POST /api/v1/create-order request body."""
    cart_value: float = Field(..., gt=0, description="Cart value in INR")
    discount_applied: float = Field(default=0, ge=0, description="Discount in INR")


class ThresholdUpdateRequest(BaseModel):
    """PUT /api/v1/dashboard/threshold request body."""
    threshold: float = Field(..., ge=0.0, le=1.0, description="Risk threshold 0.0-1.0")


class FailureLogCreate(BaseModel):
    """POST /api/v1/dashboard/failures request body."""
    error_type: str = Field(..., description="Type of failure or error")
    error_message: str = Field(..., description="Description of error")
    fallback_action: Optional[str] = Field(default="COD_ALLOWED_DEFAULT", description="Action taken on fallback")



# ═══════════════════════════════════════════════════════════════════════════════
# Response Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class CheckoutUIRules(BaseModel):
    """Dynamic checkout UI configuration."""
    cod_supported: bool
    discount_incentive_active: bool
    discount_amount_in_paise: int
    display_message: Optional[str] = None


class AuditTrail(BaseModel):
    """ML decision explainability for audit."""
    top_risk_factors: list[str]


class RiskEvaluationResponse(BaseModel):
    """POST /api/v1/evaluate-risk response body."""
    risk_score: float
    rto_probability_category: str  # "LOW", "MEDIUM", "HIGH", "UNKNOWN"
    checkout_ui_rules: CheckoutUIRules
    audit_trail: AuditTrail


class CreateOrderResponse(BaseModel):
    """POST /api/v1/create-order response body."""
    order_id: str
    amount_in_paise: int
    currency: str = "INR"
    status: str


class DashboardMetrics(BaseModel):
    """GET /api/v1/dashboard/metrics response."""
    total_evaluations: int
    rto_prevented: int
    cod_blocked: int
    total_false_positives_estimate: int
    net_margin_saved_inr: float
    avg_risk_score: float
    current_threshold: float


class AuditLogEntry(BaseModel):
    """Single entry in the audit ledger."""
    order_id: str
    timestamp: str
    risk_score: float
    rto_category: str
    action_taken: str  # "COD_BLOCKED" or "COD_ALLOWED"
    top_risk_factors: list[str]
    cart_value: float
    pincode: str
    shipping_address: str


class FailureLogEntry(BaseModel):
    """Failure/degradation event log entry."""
    timestamp: str
    error_type: str
    error_message: str
    fallback_action: str
