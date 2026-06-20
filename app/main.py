from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes import agents, orders, payments, auth_route, notifications
from app.config import settings


# ============================================================
# CREATE DATABASE TABLES
# ============================================================
# Development note:
# This creates tables if they do not already exist.
# Existing tables will not be deleted.
#
# Production note:
# For real production, Alembic migrations are better than create_all.
# But for your current deployment timeline, this can stay for now.

Base.metadata.create_all(bind=engine)


# ============================================================
# FASTAPI APP CONFIGURATION
# ============================================================

app = FastAPI(
    title="PP Services API",
    version="1.0.0",
)


# ============================================================
# CORS CONFIGURATION
# ============================================================
# Required for cookie-based authentication:
# allow_credentials=True
#
# Do not use allow_origins=["*"] with credentials.
# You must list frontend URLs exactly.

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Optional production frontend URL from .env
if settings.FRONTEND_URL:
    allowed_origins.append(settings.FRONTEND_URL)


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API ROUTES
# ============================================================

app.include_router(auth_route.router)
app.include_router(agents.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(notifications.router)


# ============================================================
# ROOT API
# ============================================================

@app.get("/")
def root():
    return {
        "message": "PP Services FastAPI backend running"
    }


# ============================================================
# HEALTH CHECK API
# ============================================================

@app.get("/api/health")
def health():
    return {
        "success": True,
        "message": "Backend connected successfully"
    }