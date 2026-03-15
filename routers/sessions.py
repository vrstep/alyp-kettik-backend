import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth_dependency import get_current_user
from database import (
    create_session,
    get_active_session,
    get_session_by_id,
    update_session_status,
    add_cart_item,
    get_cart_items,
    update_cart_item_qty,
    remove_cart_item,
    get_product_by_id,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


# ── Pydantic models ───────────────────────────────────────────────────────────

class EnterStoreRequest(BaseModel):
    qr_payload: str  # The store's QR code content, e.g. "STORE-001"


class AddCartItemRequest(BaseModel):
    product_id: int
    quantity: int = 1


class UpdateCartItemRequest(BaseModel):
    quantity: int


# ── Session lifecycle ──────────────────────────────────────────────────────────

@router.post("/enter")
async def enter_store(req: EnterStoreRequest, user: dict = Depends(get_current_user)):
    """User scans store QR code → creates an active shopping session."""
    # Check if user already has an active session
    active = await get_active_session(user["id"])
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active shopping session",
            headers={"X-Session-Id": active["id"]},
        )

    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    session = await create_session(session_id, user["id"], req.qr_payload)
    return {"session": session, "message": "Welcome to the store!"}


@router.get("/active")
async def get_active(user: dict = Depends(get_current_user)):
    """Get the user's current active shopping session."""
    session = await get_active_session(user["id"])
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active shopping session",
        )
    items = await get_cart_items(session["id"])
    total = sum(item["price"] * item["quantity"] for item in items)
    return {"session": session, "cart_items": items, "total": total}


@router.post("/complete")
async def complete_session(user: dict = Depends(get_current_user)):
    """End the current shopping session (ready for checkout)."""
    session = await get_active_session(user["id"])
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active session to complete",
        )
    await update_session_status(session["id"], "completed")
    items = await get_cart_items(session["id"])
    total = sum(item["price"] * item["quantity"] for item in items)
    return {
        "message": "Session completed",
        "session_id": session["id"],
        "cart_items": items,
        "total": total,
    }


# ── Cart operations (scoped to session) ───────────────────────────────────────

@router.get("/{session_id}/cart")
async def session_cart(session_id: str, user: dict = Depends(get_current_user)):
    """Get all items in the session cart."""
    session = await get_session_by_id(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    items = await get_cart_items(session_id)
    total = sum(item["price"] * item["quantity"] for item in items)
    return {"cart_items": items, "total": total}


@router.post("/{session_id}/cart")
async def add_to_cart(
    session_id: str,
    req: AddCartItemRequest,
    user: dict = Depends(get_current_user),
):
    """Add a product to the session cart."""
    session = await get_session_by_id(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    product = await get_product_by_id(req.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    item = await add_cart_item(session_id, req.product_id, req.quantity)
    return {"cart_item": item}


@router.put("/{session_id}/cart/{item_id}")
async def update_item(
    session_id: str,
    item_id: int,
    req: UpdateCartItemRequest,
    user: dict = Depends(get_current_user),
):
    """Update the quantity of a cart item."""
    session = await get_session_by_id(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    await update_cart_item_qty(item_id, req.quantity)
    return {"message": "Updated"}


@router.delete("/{session_id}/cart/{item_id}")
async def delete_item(
    session_id: str,
    item_id: int,
    user: dict = Depends(get_current_user),
):
    """Remove an item from the session cart."""
    session = await get_session_by_id(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")
    removed = await remove_cart_item(item_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Cart item not found")
    return {"message": "Removed"}
