from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Role
from app.schemas import UserLogin, TokenResponse, UserResponse
from app.auth import (
    verify_password,
    create_access_token,
    get_current_user,
)


# ============================================================
# AUTH ROUTES
# ============================================================
# Purpose:
# This file handles real backend authentication.
#
# Routes:
# 1. POST /api/auth/login
# 2. GET  /api/auth/me
#
# Login flow:
# Frontend sends email + password.
# Backend checks users table.
# Backend verifies password.
# Backend returns JWT token + user details.


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


# ============================================================
# HELPER FUNCTION: BUILD USER RESPONSE
# ============================================================

def build_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role.name if user.role else "",
        agent_id=user.agent_id,
        status=user.status,
    )


# ============================================================
# LOGIN API
# ============================================================
# URL:
# POST /api/auth/login
#
# Request body:
# {
#   "email": "super@admin.com",
#   "password": "admin123"
# }
#
# Response:
# {
#   "access_token": "...",
#   "token_type": "bearer",
#   "user": {
#       "id": 1,
#       "name": "Super Admin",
#       "email": "super@admin.com",
#       "role": "super_admin",
#       "agent_id": null,
#       "status": "Active"
#   }
# }

@router.post("/login", response_model=TokenResponse)
def login_user(
    login_data: UserLogin,
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.email == login_data.email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.status != "Active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    password_ok = verify_password(
        plain_password=login_data.password,
        hashed_password=user.hashed_password,
    )

    if not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user_role = user.role.name if user.role else ""

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "email": user.email,
            "role": user_role,
        }
    )

    user.last_login = str(date.today())
    db.commit()
    db.refresh(user)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=build_user_response(user),
    )


# ============================================================
# CURRENT USER API
# ============================================================
# URL:
# GET /api/auth/me
#
# Purpose:
# Frontend can call this API using token to verify current user.
#
# Header:
# Authorization: Bearer token_here

@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return build_user_response(current_user)