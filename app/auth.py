from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


# ============================================================
# AUTHENTICATION AND AUTHORIZATION FILE
# ============================================================
# Purpose:
# This file handles all backend authentication and permission logic.
#
# It provides:
# 1. Password hashing
# 2. Password verification
# 3. JWT access token creation
# 4. Current logged-in user detection
# 5. Role-based permission checking
#
# Used by:
# - auth.py route for login
# - agents.py for member access protection
# - orders.py for job access protection
# - payments.py for payment access protection


# ============================================================
# JWT CONFIGURATION
# ============================================================
# SECRET_KEY:
# This is used to sign JWT tokens.
#
# Important:
# In production, do not keep this hardcoded.
# Later move this value into .env file.
#
# Example later:
# SECRET_KEY = settings.SECRET_KEY

SECRET_KEY = "change-this-secret-key-later"


# JWT signing algorithm.
# HS256 is commonly used for simple JWT authentication.
ALGORITHM = "HS256"


# Token expiry time.
# 60 * 24 = 1440 minutes = 1 day.
#
# Meaning:
# User login token will be valid for 1 day.
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


# ============================================================
# PASSWORD HASHING CONFIGURATION
# ============================================================
# We use passlib with bcrypt.
#
# Why hashing is needed:
# Never store plain passwords in database.
#
# Example:
# User password: admin123
#
# Database should not store:
# admin123
#
# Database should store hashed value like:
# $2b$12$xxxxxx...
#
# During login:
# - User types plain password
# - We compare it with hashed password
# - If match, login success

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


# ============================================================
# HASH PASSWORD
# ============================================================
# Purpose:
# Converts plain password into secure hashed password.
#
# Used when:
# - Creating Super Admin
# - Creating Admin
# - Creating Agent login
#
# Example:
# hash_password("admin123")
# returns bcrypt hashed password

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


# ============================================================
# VERIFY PASSWORD
# ============================================================
# Purpose:
# Checks whether plain password matches hashed password.
#
# Used during login.
#
# Example:
# plain_password = "admin123"
# hashed_password = "$2b$12$..."
#
# If correct:
# returns True
#
# If wrong:
# returns False

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password,
    )


# ============================================================
# CREATE JWT ACCESS TOKEN
# ============================================================
# Purpose:
# Creates a signed JWT token after successful login.
#
# Token contains user information like:
# - user id
# - email
# - role
# - expiry time
#
# Important:
# Do not store sensitive data like password inside token.
#
# Example payload:
# {
#   "sub": "1",
#   "email": "super@admin.com",
#   "role": "super_admin",
#   "exp": expiry_time
# }

def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    # Copy original data so original dictionary is not modified.
    to_encode = data.copy()

    # Set token expiry time.
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # Add expiry time into token payload.
    to_encode.update(
        {
            "exp": expire,
        }
    )

    # Create signed JWT token.
    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    return encoded_jwt


# ============================================================
# OAUTH2 TOKEN READER
# ============================================================
# Purpose:
# Reads Bearer token from request header.
#
# Frontend will send token like:
#
# Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
#
# OAuth2PasswordBearer automatically extracts the token.
#
# tokenUrl is only for Swagger UI.
# It tells Swagger where login happens.

bearer_scheme = HTTPBearer()

# ============================================================
# GET CURRENT LOGGED-IN USER
# ============================================================
# Purpose:
# Reads JWT token, verifies it, and returns current user from database.
#
# Used in protected APIs.
#
# Example:
# current_user: User = Depends(get_current_user)
#
# If token is valid:
# returns User object
#
# If token is missing/invalid/expired:
# raises 401 Unauthorized

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    try:
        token = credentials.credentials

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = (
        db.query(User)
        .filter(User.id == int(user_id))
        .first()
    )

    if not user:
        raise credentials_exception

    if user.status != "Active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    return user


# ============================================================
# ROLE-BASED PERMISSION CHECKER
# ============================================================
# Purpose:
# Allows only selected roles to access specific APIs.
#
# Example:
#
# @router.put(
#     "/{payment_id}/pay",
#     dependencies=[Depends(require_roles(["super_admin"]))]
# )
#
# Meaning:
# Only super_admin can pay commission.
#
# Another example:
#
# Depends(require_roles(["super_admin", "admin"]))
#
# Meaning:
# super_admin and admin can access.
#
# If user role is not allowed:
# returns 403 Forbidden.

def require_roles(allowed_roles: list[str]):
    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        # Get role name from related Role table.
        user_role = current_user.role.name if current_user.role else None

        # Check role permission.
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return current_user

    return role_checker


# ============================================================
# OPTIONAL HELPER: GET USER ROLE NAME
# ============================================================
# Purpose:
# Safely return current user's role name.
#
# Useful in routes where you need:
# current_user_role = get_user_role(current_user)

def get_user_role(user: User) -> Optional[str]:
    if not user or not user.role:
        return None

    return user.role.name