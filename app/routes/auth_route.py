from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Role
from app.schemas import (
    UserLogin,
    UserResponse,
    UserCreate,
    ResetPasswordRequest,
)
from app.auth import (
    verify_password,
    create_access_token,
    get_current_user,
    get_password_hash,
    require_roles,
)
from app.config import settings


# ============================================================
# AUTH ROUTES
# ============================================================
# Purpose:
# This file handles real backend authentication.
#
# Routes:
# 1. POST /api/auth/login
# 2. GET  /api/auth/me
# 3. POST /api/auth/register
# 4. POST /api/auth/logout
# 5. POST /api/auth/refresh
# 6. POST /api/auth/reset-password
#
# Auth flow:
# Frontend sends email + password.
# Backend verifies user.
# Backend creates JWT token.
# Backend stores JWT token in HttpOnly cookie.
# Frontend does not store token in localStorage.


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


# ============================================================
# COOKIE SETTINGS
# ============================================================
# Cookie security settings are read from config.py / .env:
#
# For localhost:
#   COOKIE_SECURE=false, COOKIE_SAMESITE=lax
#
# For production HTTPS:
#   COOKIE_SECURE=true, COOKIE_SAMESITE=none

COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = 60 * 60 * 24  # 1 day


def set_auth_cookie(
    response: Response,
    access_token: str,
):
    response.set_cookie(
        key=COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=COOKIE_MAX_AGE,
        path="/",
    )


def clear_auth_cookie(response: Response):
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        samesite=settings.COOKIE_SAMESITE,
        secure=settings.COOKIE_SECURE,
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
        must_reset_password=user.must_reset_password,
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
#   "message": "Login successful",
#   "user": {
#       "id": 1,
#       "name": "Super Admin",
#       "email": "super@admin.com",
#       "role": "super_admin",
#       "agent_id": null,
#       "status": "Active",
#       "must_reset_password": false
#   }
# }
#
# Token is stored in HttpOnly cookie.

@router.post("/login")
def login_user(
    login_data: UserLogin,
    response: Response,
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

    set_auth_cookie(
        response=response,
        access_token=access_token,
    )

    user.last_login = str(date.today())

    db.commit()
    db.refresh(user)

    return {
        "message": "Login successful",
        "user": build_user_response(user),
    }


# ============================================================
# CURRENT USER API
# ============================================================
# URL:
# GET /api/auth/me
#
# Purpose:
# Frontend calls this API to check current logged-in user.
# Backend reads JWT from HttpOnly cookie.

@router.get("/me", response_model=UserResponse)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return build_user_response(current_user)


# ============================================================
# REGISTER API
# ============================================================
# URL:
# POST /api/auth/register

@router.post("/register", response_model=UserResponse)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin"])),
):
    existing_user = (
        db.query(User)
        .filter(User.email == user_data.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    role = (
        db.query(Role)
        .filter(Role.name == user_data.role)
        .first()
    )

    if not role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    new_user = User(
        name=user_data.name,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role_id=role.id,
        agent_id=user_data.agent_id,
        status="Active",
        must_reset_password=False,
        created_date=str(date.today()),
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return build_user_response(new_user)


# ============================================================
# LOGOUT API
# ============================================================
# URL:
# POST /api/auth/logout

@router.post("/logout")
def logout_user(response: Response):
    clear_auth_cookie(response)

    return {
        "message": "Logout successful"
    }


# ============================================================
# REFRESH TOKEN API
# ============================================================
# URL:
# POST /api/auth/refresh
#
# Purpose:
# Creates a fresh token and stores it again in HttpOnly cookie.

@router.post("/refresh")
def refresh_token(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    user_role = current_user.role.name if current_user.role else ""

    access_token = create_access_token(
        data={
            "sub": str(current_user.id),
            "email": current_user.email,
            "role": user_role,
        }
    )

    set_auth_cookie(
        response=response,
        access_token=access_token,
    )

    return {
        "message": "Token refreshed successfully",
        "user": build_user_response(current_user),
    }


# ============================================================
# RESET PASSWORD API
# ============================================================
# URL:
# POST /api/auth/reset-password
#
# Purpose:
# Current logged-in user resets password.
# Backend gets user from HttpOnly cookie.
# Do not use email from frontend for this flow.

@router.post("/reset-password")
def reset_password(
    reset_data: ResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.hashed_password = get_password_hash(
        reset_data.new_password
    )

    current_user.must_reset_password = False

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Password reset successful",
        "user": build_user_response(current_user),
    }