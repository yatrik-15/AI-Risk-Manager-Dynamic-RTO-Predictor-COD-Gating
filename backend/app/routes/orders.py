"""
Razorpay order creation API route.
POST /api/v1/create-order
"""

from fastapi import APIRouter, HTTPException
from ..models.schemas import CreateOrderRequest, CreateOrderResponse
from ..utils.razorpay_client import create_razorpay_order

router = APIRouter()


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order_endpoint(request: CreateOrderRequest):
    """
    Create a Razorpay order for prepaid payment.
    Calculates amount in paise after discount.
    """
    try:
        # Calculate final amount in paise
        final_amount = max(0, request.cart_value - request.discount_applied)
        amount_in_paise = int(final_amount * 100)

        if amount_in_paise <= 0:
            raise HTTPException(status_code=400, detail="Order amount must be greater than 0")

        result = await create_razorpay_order(amount_in_paise)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Order creation failed: {str(e)}",
        )
