from typing import Optional
from pydantic import BaseModel, EmailStr


# =========================
# AGENT SCHEMAS
# =========================

class AgentCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    parent_agent_id: Optional[int] = None
    status: str = "Active"
    joined_date: Optional[str] = None

class AgentUpdate(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    parent_agent_id: Optional[int] = None
    status: str = "Active"
    joined_date: Optional[str] = None

class AgentResponse(BaseModel):
    id: int
    code: str
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    parent_agent_id: Optional[int] = None

    total_orders: int
    total_commission: float
    printing_revenue: float

    status: str
    joined_date: Optional[str] = None

    class Config:
        from_attributes = True


# =========================
# ORDER SCHEMAS
# =========================

class OrderCreate(BaseModel):
    customer_name: str
    product_name: str
    quantity: int
    unit_price: float
    printing_cost: float
    direct_agent_id: int
    delivery_date: Optional[str] = None


class OrderResponse(BaseModel):
    id: int
    order_id: str

    customer_name: str
    product_name: str

    quantity: int
    unit_price: float
    total_amount: float
    printing_cost: float

    direct_agent_id: int
    parent_agent_id: Optional[int] = None
    grandparent_agent_id: Optional[int] = None

    direct_agent_commission: float
    parent_commission: float
    grandparent_commission: float
    final_direct_agent_commission: float

    status: str
    delivery_date: Optional[str] = None
    created_date: Optional[str] = None

    class Config:
        from_attributes = True


# =========================
# OPTIONAL DASHBOARD SCHEMAS
# =========================

class DashboardSummary(BaseModel):
    total_agents: int
    total_orders: int
    pending_orders: int
    completed_orders: int
    total_revenue: float
    total_commission: float


# =========================
# OPTIONAL COMMON RESPONSE
# =========================

class MessageResponse(BaseModel):
    message: str