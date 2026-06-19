from typing import Optional
from pydantic import BaseModel, EmailStr


# ============================================================
# SCHEMAS FILE
# ============================================================
# Purpose:
# This file contains all Pydantic schemas used by FastAPI.
#
# Schemas are used for:
# 1. Request body validation
# 2. API response formatting
# 3. Data transfer between frontend and backend
#
# Important:
# SQLAlchemy models are database tables.
# Pydantic schemas are API input/output formats.


# ============================================================
# AGENT / MEMBER SCHEMAS
# ============================================================
# Agent means business member/sales person.
#
# Frontend visible name can be "Member".
# Backend/database name is still "Agent".


class AgentCreate(BaseModel):
    # Member name
    name: str

    # Member email
    email: EmailStr

    # Optional phone number
    phone: Optional[str] = None

    # Optional address
    address: Optional[str] = None

    # Parent member id.
    # If this is None, member is directly under company.
    parent_agent_id: Optional[int] = None

    # Member status: Active / Inactive
    status: str = "Active"

    # Joined date as string for now.
    # Later we can use proper Date/DateTime.
    joined_date: Optional[str] = None


class AgentUpdate(BaseModel):
    # Update member name
    name: str

    # Update member email
    email: EmailStr

    # Update phone number
    phone: Optional[str] = None

    # Update address
    address: Optional[str] = None

    # Update parent member
    parent_agent_id: Optional[int] = None

    # Update status
    status: str = "Active"

    # Update joined date
    joined_date: Optional[str] = None


class AgentResponse(BaseModel):
    # Database id
    id: int

    # Unique member code like AG001
    code: str

    # Basic member details
    name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None

    # Parent member id
    parent_agent_id: Optional[int] = None

    # Business summary
    total_orders: int
    total_commission: float
    printing_revenue: float

    # Status and date
    status: str
    joined_date: Optional[str] = None

    class Config:
        from_attributes = True


# ============================================================
# ORDER / JOB SCHEMAS
# ============================================================
# In frontend, you can show this as "Job".
# In backend/database, it is still "Order".
#
# Job flow:
# Admin/Super Admin creates job.
# Backend calculates commission.
# Backend creates commission payment records.


class OrderCreate(BaseModel):
    # ========================================================
    # BASIC JOB DETAILS
    # ========================================================

    # Customer name
    customer_name: str

    # Product/job name
    product_name: str

    # Quantity of product
    quantity: int

    # Unit price
    unit_price: float

    # Printing cost.
    # Commission is calculated from this amount.
    printing_cost: float

    # Member/agent who brought the job
    direct_agent_id: int

    # Optional delivery date
    delivery_date: Optional[str] = None

    # ========================================================
    # JOB REQUIREMENT COSTING FIELDS
    # ========================================================
    # Admin/Super Admin can type both type and amount manually.
    #
    # Total job amount will be calculated from:
    # Paper + Plate + Printing + Lamination + Binding

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
    # ========================================================
    # BASIC JOB RESPONSE
    # ========================================================

    # Database id
    id: int

    # Public job/order code like ORD-1001
    order_id: str

    # Customer and product details
    customer_name: str
    product_name: str

    # Quantity and amount details
    quantity: int
    unit_price: float
    total_amount: float

    # Printing cost used for commission calculation
    printing_cost: float

    # ========================================================
    # COMMISSION CHAIN RESPONSE
    # ========================================================

    # Direct member id
    direct_agent_id: int

    # Parent member id, if available
    parent_agent_id: Optional[int] = None

    # Grandparent member id, if available
    grandparent_agent_id: Optional[int] = None

    # Original direct commission before deduction
    direct_agent_commission: float

    # Parent commission
    parent_commission: float

    # Grandparent commission
    grandparent_commission: float

    # Final direct member commission after deductions
    final_direct_agent_commission: float

    # ========================================================
    # STATUS AND DATE RESPONSE
    # ========================================================

    # Pending / Running / Completed
    status: str

    # Delivery date
    delivery_date: Optional[str] = None

    # Created date
    created_date: Optional[str] = None

    # ========================================================
    # JOB REQUIREMENT COSTING RESPONSE
    # ========================================================

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

    # Total of all requirement amounts
    requirement_total_amount: float = 0

    class Config:
        from_attributes = True


# ============================================================
# COMMISSION PAYMENT SCHEMAS
# ============================================================
# Correct payment module:
# Company pays commission to members/agents.
#
# One job can create multiple payment rows:
# 1. Direct Member
# 2. Parent Member
# 3. Grandparent Member
#
# Example:
# ORD-1001 creates:
# PAY-1001 -> Direct Member -> ₹925
# PAY-1002 -> Parent Member -> ₹50
# PAY-1003 -> Grandparent Member -> ₹25


class CommissionPaymentResponse(BaseModel):
    # Database payment id
    id: int

    # Public payment id like PAY-1001
    payment_id: str

    # Internal order database id
    order_db_id: int

    # Public job/order id like ORD-1001
    order_id: str

    # Member/agent receiving payment
    agent_id: int
    agent_name: str

    # Direct Member / Parent Member / Grandparent Member
    agent_role: str

    # Total commission payable to this member
    commission_amount: float

    # Amount already paid by company
    paid_amount: float

    # Remaining amount to be paid
    pending_amount: float

    # Pending / Partial / Paid
    payment_status: str

    # Payment date and method
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None

    # Record dates
    created_date: Optional[str] = None
    updated_date: Optional[str] = None

    class Config:
        from_attributes = True


class CommissionPaymentUpdate(BaseModel):
    # Amount paid by company.
    # Backend will validate:
    # paid_amount must not exceed commission_amount.
    paid_amount: float

    # Payment method.
    # Example: Company Payment / Cash / Bank / UPI
    payment_method: Optional[str] = "Company Payment"


# ============================================================
# AUTH / USER SCHEMAS
# ============================================================
# These schemas are for real backend login.
#
# New auth flow:
# Frontend sends email + password.
# Backend verifies user from users table.
# Backend returns JWT token + user details.


class UserLogin(BaseModel):
    # Login email
    email: EmailStr

    # Plain password entered by user
    password: str


class UserCreate(BaseModel):
    # User full name
    name: str

    # User login email
    email: EmailStr

    # Plain password.
    # Backend will hash it before saving.
    password: str

    # Role name:
    # super_admin / admin / agent
    role: str = "agent"

    # Optional linked agent/member id.
    # Required only when creating agent login user.
    agent_id: Optional[int] = None


class UserResponse(BaseModel):
    # User database id
    id: int

    # User name
    name: str

    # User email
    email: str

    # Role name:
    # super_admin / admin / agent
    role: str

    # Linked agent/member id if user is agent
    agent_id: Optional[int] = None

    # Active / Inactive / Blocked
    status: str

    #Reset Password
    must_reset_password: bool  

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    # JWT access token
    access_token: str

    # Token type always bearer
    token_type: str = "bearer"

    # Logged-in user details
    user: UserResponse


# ============================================================
# OPTIONAL DASHBOARD SCHEMAS
# ============================================================
# This can be used later for dashboard summary API.


class DashboardSummary(BaseModel):
    total_agents: int
    total_orders: int
    pending_orders: int
    completed_orders: int
    total_revenue: float
    total_commission: float


# ============================================================
# OPTIONAL COMMON RESPONSE
# ============================================================
# Simple message response schema.
#
# Example:
# {
#   "message": "User created successfully"
# }


class MessageResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    # New plain password.
    # Backend will hash it before saving.
    new_password: str


class OrderCostingUpdate(BaseModel):
    paper_amount: float = 0
    plate_amount: float = 0
    printing_amount: float = 0
    lamination_amount: float = 0
    binding_amount: float = 0


class NotificationResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    message: str
    is_read: bool
    created_date: Optional[str] = None
    order_id: Optional[int] = None

    class Config:
        from_attributes = True