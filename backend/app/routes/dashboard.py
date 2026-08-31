"""
Merchant Dashboard API routes.
GET /api/v1/dashboard/metrics
GET /api/v1/dashboard/audit-log
PUT /api/v1/dashboard/threshold
GET /api/v1/dashboard/failures
"""

from fastapi import APIRouter, Query
from ..models.schemas import (
    DashboardMetrics,
    AuditLogEntry,
    FailureLogEntry,
    FailureLogCreate,
    ThresholdUpdateRequest,
)
from ..services.risk_engine import (
    get_dashboard_metrics,
    get_audit_log,
    get_failure_log,
    log_failure,
    set_threshold,
    get_current_threshold,
)

router = APIRouter()


@router.get("/metrics", response_model=DashboardMetrics)
async def dashboard_metrics():
    """Get aggregated dashboard metrics."""
    return get_dashboard_metrics()


@router.get("/audit-log", response_model=list[AuditLogEntry])
async def audit_log(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Get paginated audit log entries (newest first)."""
    return get_audit_log(limit=limit, offset=offset)


@router.put("/threshold")
async def update_threshold(request: ThresholdUpdateRequest):
    """Update the risk threshold for COD blocking."""
    set_threshold(request.threshold)
    return {
        "status": "updated",
        "new_threshold": request.threshold,
        "message": f"Risk threshold updated to {request.threshold:.2f}",
    }


@router.get("/threshold")
async def current_threshold():
    """Get the current risk threshold."""
    return {"threshold": get_current_threshold()}


@router.get("/failures", response_model=list[FailureLogEntry])
async def failure_log():
    """Get failure/degradation event log."""
    return get_failure_log()


@router.post("/failures")
async def create_failure_log(request: FailureLogCreate):
    """Log a degradation or failure event (e.g. from frontend timeout fallback)."""
    log_failure(
        error_type=request.error_type,
        error_message=request.error_message,
        fallback_action=request.fallback_action or "COD_ALLOWED_DEFAULT",
    )
    return {"status": "logged"}

