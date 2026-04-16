"""
Entry-token endpoints for turnstile-based session initiation.

Flow:
  1. Authenticated user requests POST /sessions/entry-qr  → gets a signed JWT entry token
  2. Phone app displays the token as a QR code
  3. Turnstile (laptop webcam) scans the QR, calls POST /sessions/turnstile-enter
  4. Backend validates the token, creates a shopping session, returns user name
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth_dependency import get_current_user, SECRET_KEY, ALGORITHM
from database import create_session, get_active_session, get_pool

router = APIRouter(prefix="/sessions", tags=["sessions"])

ENTRY_TOKEN_EXPIRE_MINUTES = 5


# ── Pydantic models ───────────────────────────────────────────────────────────

class EntryQrResponse(BaseModel):
    entry_token: str
    expires_in_seconds: int


class TurnstileEnterRequest(BaseModel):
    entry_token: str


# ── DB helpers for used entry tokens ──────────────────────────────────────────

async def _ensure_entry_tokens_table():
    """Create the used_entry_tokens table if it doesn't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS used_entry_tokens (
                jti         TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                used_at     TIMESTAMPTZ DEFAULT NOW()
            )
        """)


async def _is_token_used(jti: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM used_entry_tokens WHERE jti = $1", jti
        )
        return row is not None


async def _mark_token_used(jti: str, user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO used_entry_tokens (jti, user_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            jti, user_id,
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/entry-qr", response_model=EntryQrResponse)
async def generate_entry_qr(user: dict = Depends(get_current_user)):
    """
    Authenticated user requests a one-time entry QR token.
    Returns a short-lived JWT that the turnstile will scan.
    """
    jti = uuid.uuid4().hex
    exp = datetime.now(timezone.utc) + timedelta(minutes=ENTRY_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_id": user["id"],
        "jti": jti,
        "purpose": "store_entry",
        "exp": exp,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {
        "entry_token": token,
        "expires_in_seconds": ENTRY_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/turnstile-enter")
async def turnstile_enter(req: TurnstileEnterRequest):
    """
    Called by the turnstile device after scanning a QR code.
    No Bearer auth needed – the turnstile is a trusted device, and
    the entry_token itself proves the user's identity.
    """
    # 1. Decode and validate the entry token
    try:
        payload = jwt.decode(req.entry_token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Entry QR code has expired. Please generate a new one.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid QR code.",
        )

    # 2. Check purpose claim
    if payload.get("purpose") != "store_entry":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR code type.",
        )

    user_id = payload["user_id"]
    jti = payload["jti"]

    # 3. One-time use check
    if await _is_token_used(jti):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This QR code has already been used.",
        )

    # 4. Check if user already has an active session
    active = await get_active_session(user_id)
    if active:
        # Mark token as used to prevent replay
        await _mark_token_used(jti, user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has an active shopping session.",
        )

    # 5. Mark token used + create session
    await _mark_token_used(jti, user_id)
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    session = await create_session(session_id, user_id, "TURNSTILE-001")

    # 6. Get user name for the turnstile display
    from database import get_user_by_id
    user = await get_user_by_id(user_id)
    user_name = user["name"] if user else "Customer"

    return {
        "success": True,
        "message": f"Welcome, {user_name}!",
        "user_name": user_name,
        "session_id": session_id,
    }
