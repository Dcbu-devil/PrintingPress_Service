from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes import agents, orders

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="PP Services API",
    version="1.0.0",
)

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

app.include_router(agents.router)
app.include_router(orders.router)


@app.get("/")
def root():
    return {
        "message": "PP Services FastAPI backend running"
    }


@app.get("/api/health")
def health():
    return {
        "success": True,
        "message": "Backend connected successfully"
    }