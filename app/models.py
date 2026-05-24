from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


# =========================
# AGENT / MEMBER MODEL
# =========================

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)

    # Unique member code like AG001, AG002
    code = Column(String, unique=True, index=True)

    # Basic member details
    name = Column(String, nullable=False, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    address = Column(String)

    # Parent member ID for hierarchy
    # If null, this member is directly under company
    parent_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)

    # Member business summary
    total_orders = Column(Integer, default=0)
    total_commission = Column(Float, default=0)
    printing_revenue = Column(Float, default=0)

    # Member status
    status = Column(String, default="Active")
    joined_date = Column(String)

    # Self relationship for parent-child hierarchy
    parent = relationship("Agent", remote_side=[id])


# =========================
# ORDER / JOB MODEL
# =========================

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    # =========================
    # BASIC JOB DETAILS
    # =========================

    order_id = Column(String, unique=True, index=True)
    customer_name = Column(String, nullable=False)
    product_name = Column(String, nullable=False)

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    printing_cost = Column(Float, nullable=False)

    # =========================
    # JOB REQUIREMENT COSTING FIELDS
    # =========================
    # These fields store the 5 requirement costs:
    # Paper, Plate, Printing, Lamination, Binding

    paper_type = Column(String, nullable=True)
    paper_amount = Column(Float, default=0)

    plate_type = Column(String, nullable=True)
    plate_amount = Column(Float, default=0)

    printing_type = Column(String, nullable=True)
    printing_amount = Column(Float, default=0)

    lamination_type = Column(String, nullable=True)
    lamination_amount = Column(Float, default=0)

    binding_type = Column(String, nullable=True)
    binding_amount = Column(Float, default=0)

    # Sum of all 5 amounts:
    # paper_amount + plate_amount + printing_amount
    # + lamination_amount + binding_amount
    requirement_total_amount = Column(Float, default=0)

    # =========================
    # MEMBER / AGENT COMMISSION CHAIN
    # =========================

    direct_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    parent_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    grandparent_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)

    direct_agent_commission = Column(Float, default=0)
    parent_commission = Column(Float, default=0)
    grandparent_commission = Column(Float, default=0)
    final_direct_agent_commission = Column(Float, default=0)

    # =========================
    # JOB STATUS AND DATES
    # =========================

    status = Column(String, default="Pending")
    delivery_date = Column(String)
    created_date = Column(String)

    # =========================
    # OLD PAYMENT FIELDS
    # =========================
    # These fields were added earlier.
    # We will keep them for safety, but the correct payment module
    # will use CommissionPayment table below.

    agent_paid_amount = Column(Float, default=0)
    payment_status = Column(String, default="Pending")
    payment_date = Column(String)
    payment_method = Column(String)

    # Relationship with direct member/agent
    direct_agent = relationship("Agent", foreign_keys=[direct_agent_id])


# =========================
# COMMISSION PAYMENT MODEL
# =========================
# This is the correct payment module table.
# It stores company-to-member commission payments.
#
# Example:
# One job can create 3 payment rows:
# 1. Direct Member payment
# 2. Parent Member payment
# 3. Grandparent Member payment

class CommissionPayment(Base):
    __tablename__ = "commission_payments"

    id = Column(Integer, primary_key=True, index=True)

    # Unique payment code like PAY-1001, PAY-1002
    payment_id = Column(String, unique=True, index=True)

    # Job/order reference
    order_db_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    order_id = Column(String, nullable=False)

    # Member/agent who will receive payment
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    agent_name = Column(String, nullable=False)

    # Example values:
    # Direct Member, Parent Member, Grandparent Member
    agent_role = Column(String, nullable=False)

    # Actual commission company has to pay
    commission_amount = Column(Float, default=0)

    # Amount company already paid
    paid_amount = Column(Float, default=0)

    # Remaining amount company has to pay
    pending_amount = Column(Float, default=0)

    # Pending / Partial / Paid
    payment_status = Column(String, default="Pending")

    # Payment info
    payment_date = Column(String)
    payment_method = Column(String)

    # Dates
    created_date = Column(String)
    updated_date = Column(String)

    # Relationships
    order = relationship("Order", foreign_keys=[order_db_id])
    agent = relationship("Agent", foreign_keys=[agent_id])