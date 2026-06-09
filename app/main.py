from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes import agents, orders, payments, auth



# =========================
# CREATE DATABASE TABLES
# =========================
# This creates tables if they do not already exist.
# Existing tables will not be deleted.

Base.metadata.create_all(bind=engine)


# =========================
# FASTAPI APP CONFIGURATION
# =========================

app = FastAPI(
    title="PP Services API",
    version="1.0.0",
)


# =========================
# CORS CONFIGURATION
# =========================
# This allows your React frontend to connect with FastAPI backend.

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# API ROUTES
# =========================

app.include_router(agents.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(auth.router)

# =========================
# ROOT API
# =========================

@app.get("/")
def root():
    return {
        "message": "PP Services FastAPI backend running"
    }


# =========================
# HEALTH CHECK API
# =========================

@app.get("/api/health")
def health():
    return {
        "success": True,
        "message": "Backend connected successfully"
    }