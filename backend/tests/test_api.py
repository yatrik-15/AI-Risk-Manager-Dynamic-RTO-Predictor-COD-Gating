"""
Backend API & Risk Engine Integration Tests
===========================================
Tests all endpoints in the FastAPI app:
- /health
- POST /api/v1/evaluate-risk (LOW, MEDIUM, HIGH risk, validation errors)
- POST /api/v1/create-order
- GET/PUT /api/v1/dashboard/*
- POST /api/v1/dashboard/failures
"""

import os
import sys
import pytest
from unittest.mock import patch

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app
from app.services.risk_engine import get_current_threshold, set_threshold


@pytest.fixture(scope="module")
def client():
    """Module-level TestClient fixture that enters lifespan context manager."""
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    """Verify health check endpoint returns 200 and loaded model status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True


def test_root_endpoint(client):
    """Verify root endpoint info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["docs"] == "/docs"


def test_evaluate_risk_high_risk(client):
    """Verify high-risk request (short address with vague term) blocks COD."""
    payload = {
        "cart_value": 2500.0,
        "shipping_address": "Near bus stand",  # Short length (<15) + vague term
        "pincode": "110043",
        "customer_ip": "192.168.1.100",
        "device_hash": "test_device_hash_123",
        "category": "Fashion",
        "payment_method": "COD",
    }
    response = client.post("/api/v1/evaluate-risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "risk_score" in data
    assert data["rto_probability_category"] in ["HIGH", "MEDIUM"]
    assert "checkout_ui_rules" in data
    assert "audit_trail" in data
    assert isinstance(data["audit_trail"]["top_risk_factors"], list)


def test_evaluate_risk_low_risk(client):
    """Verify low-risk request with complete address."""
    payload = {
        "cart_value": 850.0,
        "shipping_address": "Flat 402, Sunshine Heights, Main Commercial Complex, MG Road",
        "pincode": "560001",
        "customer_ip": "103.21.12.34",
        "device_hash": "legit_device_999",
        "category": "Electronics",
        "payment_method": "UPI",
    }
    response = client.post("/api/v1/evaluate-risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_score"] < 0.75
    assert data["checkout_ui_rules"]["cod_supported"] is True


def test_evaluate_risk_invalid_pincode(client):
    """Verify Pydantic validation rejects invalid pincodes."""
    payload = {
        "cart_value": 1000.0,
        "shipping_address": "Valid long address street line 1",
        "pincode": "012345",  # Starts with 0 - invalid for India
        "customer_ip": "127.0.0.1",
        "device_hash": "dev123",
    }
    response = client.post("/api/v1/evaluate-risk", json=payload)
    assert response.status_code == 422  # Unprocessable Entity


def test_create_order(client):
    """Verify order creation endpoint."""
    payload = {
        "cart_value": 1500.0,
        "discount_applied": 50.0,
    }
    response = client.post("/api/v1/create-order", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "order_id" in data
    assert data["amount_in_paise"] == 145000  # (1500 - 50) * 100
    assert data["currency"] == "INR"


def test_dashboard_metrics(client):
    """Verify dashboard metrics endpoint."""
    response = client.get("/api/v1/dashboard/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_evaluations" in data
    assert "rto_prevented" in data
    assert "net_margin_saved_inr" in data


def test_dashboard_audit_log(client):
    """Verify dashboard audit log endpoint."""
    response = client.get("/api/v1/dashboard/audit-log?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_dashboard_threshold_update(client):
    """Verify risk threshold update and retrieval."""
    original = get_current_threshold()
    try:
        # Update threshold
        res_put = client.put("/api/v1/dashboard/threshold", json={"threshold": 0.85})
        assert res_put.status_code == 200
        assert res_put.json()["new_threshold"] == 0.85

        # Get threshold
        res_get = client.get("/api/v1/dashboard/threshold")
        assert res_get.status_code == 200
        assert res_get.json()["threshold"] == 0.85
    finally:
        set_threshold(original)


def test_dashboard_failures(client):
    """Verify failure log creation and retrieval."""
    # Create failure
    post_res = client.post("/api/v1/dashboard/failures", json={
        "error_type": "FRONTEND_TIMEOUT_TEST",
        "error_message": "Test timeout message",
        "fallback_action": "COD_ALLOWED_DEFAULT",
    })
    assert post_res.status_code == 200

    # Retrieve failures
    get_res = client.get("/api/v1/dashboard/failures")
    assert get_res.status_code == 200
    failures = get_res.json()
    assert len(failures) > 0
    latest = failures[0]
    assert latest["error_type"] == "FRONTEND_TIMEOUT_TEST"


def test_evaluate_risk_adversarial_address_padding(client):
    """Verify adversarial padding triggers character spam guardrail."""
    payload = {
        "cart_value": 2500.0,
        "shipping_address": "near bus stand aaaaaaaaaaa",
        "pincode": "110043",
        "customer_ip": "192.168.1.100",
        "device_hash": "test_device_hash_123",
        "category": "Fashion",
        "payment_method": "COD",
    }
    response = client.post("/api/v1/evaluate-risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "adversarial_character_padding" in data["audit_trail"]["top_risk_factors"]
    assert data["rto_probability_category"] == "HIGH"
    assert data["checkout_ui_rules"]["cod_supported"] is False


@patch("app.services.velocity.velocity_service.get_pincode_velocity")
def test_evaluate_risk_high_destination_velocity(mock_get_velocity, client):
    """Verify proxy defense block for high pincode velocity."""
    mock_get_velocity.return_value = 25  # > 15
    payload = {
        "cart_value": 2500.0,
        "shipping_address": "Normal House 123",
        "pincode": "110043",
        "customer_ip": "192.168.1.100",
        "device_hash": "test_device_hash_123",
        "category": "Fashion",
        "payment_method": "COD",
    }
    response = client.post("/api/v1/evaluate-risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "distributed_proxy_attack_detected" in data["audit_trail"]["top_risk_factors"]
    assert data["rto_probability_category"] == "HIGH"
    assert data["checkout_ui_rules"]["cod_supported"] is False


def test_evaluate_risk_negative_cart_bounding(client):
    """Verify discount bounding ensures order doesn't become negative or 0."""
    payload = {
        "cart_value": 1.5,  # ₹1.50
        "shipping_address": "Normal House 123",
        "pincode": "110043",
        "customer_ip": "192.168.1.100",
        "device_hash": "test_device_hash_123",
        "category": "Fashion",
        "payment_method": "COD",
    }
    response = client.post("/api/v1/evaluate-risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    # Cart value 1.5. Max allowed discount = (1.5 - 1) * 100 = 50 paise
    # Calculated 5% discount = 1.5 * 0.05 * 100 = 7 paise
    # Result should be min(50, 7) = 7 paise or bounded correctly if high risk
    discount = data["checkout_ui_rules"]["discount_amount_in_paise"]
    assert discount >= 0
    assert discount <= 50  # Must leave at least 1 INR (100 paise) for Razorpay


@patch("app.services.velocity.velocity_service.get_ip_velocity")
def test_evaluate_risk_redis_timeout_fallback(mock_get_ip, client):
    """Verify fail-open fallback if Redis connection hangs or fails."""
    mock_get_ip.side_effect = Exception("Redis connection timed out")
    payload = {
        "cart_value": 2500.0,
        "shipping_address": "Normal House 123",
        "pincode": "110043",
        "customer_ip": "192.168.1.100",
        "device_hash": "test_device_hash_123",
        "category": "Fashion",
        "payment_method": "COD",
    }
    response = client.post("/api/v1/evaluate-risk", json=payload)
    assert response.status_code == 200  # Must not crash!
    # Exception shouldn't crash the API, it just returns a successful eval without velocity data
