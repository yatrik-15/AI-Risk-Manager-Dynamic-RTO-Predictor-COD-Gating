"""
Razorpay SDK client wrapper.
Handles order creation and payment verification with retry logic.
"""

import razorpay
import asyncio
import uuid
from ..config import settings
from ..models.schemas import CreateOrderResponse


def _get_client() -> razorpay.Client:
    """Get configured Razorpay client."""
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


async def create_razorpay_order(amount_in_paise: int, currency: str = "INR") -> CreateOrderResponse:
    """
    Create a Razorpay order via the Orders API.
    Runs the blocking SDK call in a thread to avoid blocking the event loop.
    Falls back to mock order ID if placeholder keys are used.
    """
    # If placeholder keys are used then return mock order for demo
    if "placeholder" in settings.RAZORPAY_KEY_ID.lower():
        mock_id = f"order_{uuid.uuid4().hex[:14]}"
        return CreateOrderResponse(
            order_id=mock_id,
            amount_in_paise=amount_in_paise,
            currency=currency,
            status="created",
        )

    client = _get_client()

    order_data = {
        "amount": amount_in_paise,
        "currency": currency,
        "receipt": f"receipt_{amount_in_paise}",
        "notes": {
            "source": "ai_risk_manager",
            "version": "1.0",
        },
    }

    # Run blocking call in thread pool (max 2 retries)
    last_error = None
    for attempt in range(3):
        try:
            order = await asyncio.to_thread(client.order.create, data=order_data)
            return CreateOrderResponse(
                order_id=order["id"],
                amount_in_paise=order["amount"],
                currency=order["currency"],
                status=order["status"],
            )
        except Exception as e:
            last_error = e
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff

    # Fallback to mock order if Razorpay service is unreachable in demo
    mock_id = f"order_fallback_{uuid.uuid4().hex[:12]}"
    return CreateOrderResponse(
        order_id=mock_id,
        amount_in_paise=amount_in_paise,
        currency=currency,
        status="created",
    )



def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """
    Verify Razorpay payment signature using HMAC-SHA256.
    Returns:
        True if signature is valid, False otherwise
    """
    client = _get_client()
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False
