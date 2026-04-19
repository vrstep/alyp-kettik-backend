import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth_dependency import get_current_user
from database import (
    create_payment_method,
    get_payment_methods,
    delete_payment_method,
    set_default_payment_method,
    create_order,
    get_user_orders,
    get_order_detail,
    get_active_session,
    get_cart_items,
    update_session_status,
)

router = APIRouter(prefix="/payment", tags=["payment"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class AddPaymentMethodRequest(BaseModel):
    card_type: str      # 'visa' or 'mastercard'
    last_four: str      # last 4 digits, e.g. '4242'
    holder_name: str    # e.g. 'JOHN DOE'
    expiry: str         # e.g. '12/28'


class PayRequest(BaseModel):
    session_id: str
    payment_method_id: int


# ── Payment method CRUD ───────────────────────────────────────────────────────

@router.get("/methods")
async def list_methods(user: dict = Depends(get_current_user)):
    """List all saved payment methods for the current user."""
    methods = await get_payment_methods(user["id"])
    return {"methods": methods}


@router.post("/methods", status_code=201)
async def add_method(req: AddPaymentMethodRequest, user: dict = Depends(get_current_user)):
    """Add a new payment method (mock card)."""
    if req.card_type not in ("visa", "mastercard"):
        raise HTTPException(400, "card_type must be 'visa' or 'mastercard'")
    if len(req.last_four) != 4 or not req.last_four.isdigit():
        raise HTTPException(400, "last_four must be exactly 4 digits")
    if not req.holder_name.strip():
        raise HTTPException(400, "holder_name is required")
    if not req.expiry.strip():
        raise HTTPException(400, "expiry is required")

    method = await create_payment_method(
        user_id=user["id"],
        card_type=req.card_type,
        last_four=req.last_four,
        holder_name=req.holder_name.upper(),
        expiry=req.expiry,
    )
    return {"method": method}


@router.delete("/methods/{method_id}")
async def remove_method(method_id: int, user: dict = Depends(get_current_user)):
    """Delete a saved payment method."""
    deleted = await delete_payment_method(method_id, user["id"])
    if not deleted:
        raise HTTPException(404, "Payment method not found")
    return {"message": "Deleted"}


@router.put("/methods/{method_id}/default")
async def make_default(method_id: int, user: dict = Depends(get_current_user)):
    """Set a payment method as the default."""
    ok = await set_default_payment_method(method_id, user["id"])
    if not ok:
        raise HTTPException(404, "Payment method not found")
    return {"message": "Default updated"}


# ── Mock payment (checkout) ────────────────────────────────────────────────────

@router.post("/pay")
async def pay(req: PayRequest, user: dict = Depends(get_current_user)):
    """
    Mock payment: validates session & card, creates order, completes session.
    Always succeeds (no real payment gateway).
    """
    # 1. Validate session
    from database import get_session_by_id
    session = await get_session_by_id(req.session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(404, "Session not found")
    if session["status"] != "active":
        raise HTTPException(400, "Session is not active")

    # 2. Validate payment method
    methods = await get_payment_methods(user["id"])
    method = next((m for m in methods if m["id"] == req.payment_method_id), None)
    if not method:
        raise HTTPException(404, "Payment method not found")

    # 3. Fetch cart items and compute total
    cart_items = await get_cart_items(req.session_id)
    if not cart_items:
        raise HTTPException(400, "Cart is empty")

    total = sum(float(item["price"]) * item["quantity"] for item in cart_items)

    # 4. Create order
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
    items_for_order = [
        {
            "product_id": item["product_id"],
            "name": item["name"],
            "price": float(item["price"]),
            "quantity": item["quantity"],
        }
        for item in cart_items
    ]

    order = await create_order(
        order_id=order_id,
        user_id=user["id"],
        session_id=req.session_id,
        payment_method_id=req.payment_method_id,
        total=total,
        items=items_for_order,
    )

    # 5. Complete session
    await update_session_status(req.session_id, "completed")

    return {
        "message": "Payment successful",
        "order": {
            "id": order_id,
            "total": total,
            "status": "paid",
            "item_count": len(cart_items),
            "card_type": method["card_type"],
            "last_four": method["last_four"],
        },
    }


# ── Order history ──────────────────────────────────────────────────────────────

@router.get("/orders")
async def list_orders(user: dict = Depends(get_current_user)):
    """List all past orders for the current user."""
    orders = await get_user_orders(user["id"])
    return {"orders": orders}


@router.get("/orders/{order_id}")
async def order_detail(order_id: str, user: dict = Depends(get_current_user)):
    """Get full order detail with all items."""
    detail = await get_order_detail(order_id, user["id"])
    if not detail:
        raise HTTPException(404, "Order not found")
    return {"order": detail}
