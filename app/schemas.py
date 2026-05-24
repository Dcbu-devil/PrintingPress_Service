from typing import Optional
from pydantic import BaseModel, EmailStr


# =========================
# AGENT / MEMBER SCHEMAS
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
    email: EmailStr
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
# ORDER / JOB SCHEMAS
# =========================

class OrderCreate(BaseModel):
    # Basic job details
    customer_name: str
    product_name: str

    # Old job/order fields
    quantity: int
    unit_price: float
    printing_cost: float

    # Member/agent who brought the job
    direct_agent_id: int

    # Optional delivery date
    delivery_date: Optional[str] = None

    # =========================
    # JOB REQUIREMENT COSTING FIELDS
    # =========================
    # Super Admin/Admin can type both type and amount manually.

    paper_type: Optional[str] = None
    paper_amount: float = 0

    plate_type: Optional[str] = None
    plate_amount: float = 0

    printing_type: Optional[str] = None
    printing_amount: float = 0

    lamination_type: Optional[str] = None
    lamination_amount: float = 0

    binding_type: Optional[str] = None
    binding_amount: float = 0


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

    # =========================
    # JOB REQUIREMENT COSTING RESPONSE
    # =========================

    paper_type: Optional[str] = None
    paper_amount: float = 0

    plate_type: Optional[str] = None
    plate_amount: float = 0

    printing_type: Optional[str] = None
    printing_amount: float = 0

    lamination_type: Optional[str] = None
    lamination_amount: float = 0

    binding_type: Optional[str] = None
    binding_amount: float = 0

    requirement_total_amount: float = 0

    class Config:
        from_attributes = True


# =========================
# COMMISSION PAYMENT SCHEMAS
# =========================
# Correct payment module:
# Company pays commission to members/agents.
#
# One job can create multiple payment rows:
# 1. Direct Member
# 2. Parent Member
# 3. Grandparent Member

class CommissionPaymentResponse(BaseModel):
    id: int
    payment_id: str

    order_db_id: int
    order_id: str

    agent_id: int
    agent_name: str
    agent_role: str

    commission_amount: float
    paid_amount: float
    pending_amount: float

    payment_status: str
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None

    created_date: Optional[str] = None
    updated_date: Optional[str] = None

    class Config:
        from_attributes = True


class CommissionPaymentUpdate(BaseModel):
    paid_amount: float
    payment_method: Optional[str] = "Company Payment"


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