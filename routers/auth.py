import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from database import create_user, get_user_by_email, update_user_profile, update_user_password
from auth_dependency import get_current_user, SECRET_KEY, ALGORITHM

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_TOKEN_EXPIRE_DAYS = 30


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── Pydantic models ───────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    created_at: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _create_token(user_id: int) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _safe_user(user: dict) -> dict:
    """Strip password_hash and serialise datetimes before returning to client."""
    out = {}
    for k, v in user.items():
        if k == "password_hash":
            continue
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(req: RegisterRequest):
    existing = await get_user_by_email(req.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    hashed = _hash_password(req.password)
    user_id = await create_user(req.email, req.name, hashed)
    user = await get_user_by_email(req.email)

    return {
        "access_token": _create_token(user_id),
        "token_type": "bearer",
        "user": _safe_user(user),
    }


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    user = await get_user_by_email(req.email)
    if not user or not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    return {
        "access_token": _create_token(user["id"]),
        "token_type": "bearer",
        "user": _safe_user(user),
    }


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    return _safe_user(user)


@router.put("/profile")
async def update_profile(req: UpdateProfileRequest, user: dict = Depends(get_current_user)):
    """Update the current user's name and/or email."""
    if req.name is None and req.email is None:
        raise HTTPException(status_code=400, detail="Nothing to update")

    # If changing email, check it's not already taken by another user
    if req.email is not None and req.email != user["email"]:
        existing = await get_user_by_email(req.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )

    updated = await update_user_profile(user["id"], name=req.name, email=req.email)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return _safe_user(updated)


@router.put("/password")
async def change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Change the current user's password (requires current password)."""
    if not _verify_password(req.current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    new_hash = _hash_password(req.new_password)
    await update_user_password(user["id"], new_hash)
    return {"message": "Password updated successfully"}
