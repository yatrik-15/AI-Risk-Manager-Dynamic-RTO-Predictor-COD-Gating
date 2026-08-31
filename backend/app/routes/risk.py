"""
Risk evaluation API route.
POST /api/v1/evaluate-risk
"""

from fastapi import APIRouter, HTTPException
from ..models.schemas import RiskEvaluationRequest, RiskEvaluationResponse
from ..services.risk_engine import evaluate_risk, log_failure

router = APIRouter()


@router.post("/evaluate-risk", response_model=RiskEvaluationResponse)
async def evaluate_risk_endpoint(request: RiskEvaluationRequest):
    """
    Evaluate RTO risk for a checkout request.
    Returns UI configuration rules (COD allowed/blocked, discount, message).
    """
    try:
        response = await evaluate_risk(request)
        return response
    except Exception as e:
        # Log the failure
        log_failure(
            error_type="ML_INFERENCE_ERROR",
            error_message=str(e),
            fallback_action="ERROR_RETURNED",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Risk evaluation failed: {str(e)}",
        )
