from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent, Order, CommissionPayment, Notification, User
from app.schemas import OrderCreate, OrderResponse, OrderCostingUpdate
from app.commission import calculate_commission
from app.auth import require_roles, get_current_user
from app.utils import generate_order_id, generate_payment_id


# ============================================================
# ORDERS / JOBS ROUTER
# ============================================================
# Purpose:
# This file manages printing jobs/orders.
#
# Main responsibilities:
# 1. Get all jobs
# 2. Create new job
# 3. Calculate commission
# 4. Create commission payment records
# 5. Update job status
#
# Permission rules:
# 1. super_admin, admin, agent can view jobs.
# 2. super_admin and admin can create jobs.
# 3. super_admin and admin can update job status.
#
# Note:
# Frontend may show this module as "Jobs".
# Backend route/table still uses "orders".

router = APIRouter(
    prefix="/api/orders",
    tags=["Orders"],
)


# ============================================================
# GET ALL JOBS / ORDERS
# ============================================================
# URL:
# GET /api/orders/
#
# Permission:
# super_admin, admin, agent
#
# Purpose:
# Returns all jobs/orders from database.
#
# Current MVP:
# Agent can see all orders.
#
# Later improvement:
# Agent should only see own orders.

@router.get(
    "/",
    response_model=list[OrderResponse],
)
def get_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role.name == "agent":
        if not current_user.agent_id:
            return []
        agent_id = current_user.agent_id
        return (
            db.query(Order)
            .filter(
                (Order.direct_agent_id == agent_id)
                | (Order.parent_agent_id == agent_id)
                | (Order.grandparent_agent_id == agent_id)
            )
            .order_by(Order.id.desc())
            .all()
        )
    return db.query(Order).order_by(Order.id.desc()).all()

# ============================================================
# GET MY JOBS / ORDERS
# ============================================================
# URL:
# GET /api/orders/my
#
# Permission:
# agent
#
# Purpose:
# Agent/member can view only own jobs.

@router.get(
    "/my",
    response_model=list[OrderResponse],
)
def get_my_orders(
    current_user: User = Depends(require_roles(["agent"])),
    db: Session = Depends(get_db),
):
    if not current_user.agent_id:
        return []

    agent_id = current_user.agent_id
    return (
        db.query(Order)
        .filter(
            (Order.direct_agent_id == agent_id)
            | (Order.parent_agent_id == agent_id)
            | (Order.grandparent_agent_id == agent_id)
        )
        .order_by(Order.id.desc())
        .all()
    )

# Payment ID generation has been moved to app/utils.py


# ============================================================
# HELPER: CREATE COMMISSION PAYMENT RECORD
# ============================================================
# Purpose:
# Creates one company-to-member commission payment record.
#
# Example:
# If job ORD-1001 creates:
#
# Direct Member       -> ₹925
# Parent Member       -> ₹50
# Grandparent Member  -> ₹25
#
# Then this function is called separately for each member.
#
# Payment is created with:
# paid_amount = 0
# pending_amount = commission_amount
# status = Pending

def create_commission_payment(
    db: Session,
    payment_id: str,
    order: Order,
    agent: Agent,
    agent_role: str,
    commission_amount: float,
):
    commission_amount = float(commission_amount or 0)

    payment = CommissionPayment(
        payment_id=payment_id,

        # Job/order reference
        order_db_id=order.id,
        order_id=order.order_id,

        # Member/agent receiving payment
        agent_id=agent.id,
        agent_name=agent.name,
        agent_role=agent_role,

        # Payment amount details
        commission_amount=commission_amount,
        paid_amount=0,
        pending_amount=commission_amount,

        # Payment status details
        payment_status="Pending",
        payment_date=None,
        payment_method=None,

        # Date tracking
        created_date=str(date.today()),
        updated_date=str(date.today()),
    )

    db.add(payment)


# ============================================================
# CREATE JOB / ORDER
# ============================================================
# URL:
# POST /api/orders/
#
# Permission:
# super_admin, admin
#
# Purpose:
# Creates a new printing job/order.
#
# Flow:
# 1. Find direct member
# 2. Find parent and grandparent
# 3. Calculate requirement total
# 4. Calculate commission
# 5. Create order record
# 6. Update member commission totals
# 7. Create commission payment records
# 8. Save everything in database

@router.post(
    "/",
    response_model=OrderResponse,
)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "admin", "agent"])),
):
    is_agent = current_user.role.name == "agent"
    if is_agent:
        if not current_user.agent_id:
            raise HTTPException(
                status_code=400,
                detail="Agent user has no connected agent/member profile",
            )
        order_data.direct_agent_id = current_user.agent_id
        order_data.paper_amount = 0
        order_data.plate_amount = 0
        order_data.printing_amount = 0
        order_data.lamination_amount = 0
        order_data.binding_amount = 0
        order_data.printing_cost = 0

    # ========================================================
    # FIND DIRECT MEMBER / AGENT
    # ========================================================

    direct_agent = (
        db.query(Agent)
        .filter(Agent.id == order_data.direct_agent_id)
        .first()
    )

    if not direct_agent:
        raise HTTPException(
            status_code=404,
            detail="Direct member not found",
        )

    # ========================================================
    # FIND PARENT AND GRANDPARENT MEMBERS
    # ========================================================
    # Direct member may have parent.
    # Parent may have grandparent.
    #
    # Only 3-level commission chain is used:
    # Direct -> Parent -> Grandparent

    parent_agent = None
    grandparent_agent = None

    if direct_agent.parent_agent_id:
        parent_agent = (
            db.query(Agent)
            .filter(Agent.id == direct_agent.parent_agent_id)
            .first()
        )

    if parent_agent and parent_agent.parent_agent_id:
        grandparent_agent = (
            db.query(Agent)
            .filter(Agent.id == parent_agent.parent_agent_id)
            .first()
        )

    # ========================================================
    # REQUIREMENT TOTAL CALCULATION
    # ========================================================
    # Total job amount is calculated from:
    #
    # Paper + Plate + Printing + Lamination + Binding

    paper_amount = float(order_data.paper_amount or 0)
    plate_amount = float(order_data.plate_amount or 0)
    printing_amount = float(order_data.printing_amount or 0)
    lamination_amount = float(order_data.lamination_amount or 0)
    binding_amount = float(order_data.binding_amount or 0)

    requirement_total_amount = (
        paper_amount
        + plate_amount
        + printing_amount
        + lamination_amount
        + binding_amount
    )

    # Note: total_amount equals requirement_total_amount by design.
    # The quantity and unit_price fields are stored as order metadata
    # but are not used in this total calculation.
    total_amount = requirement_total_amount

    # ========================================================
    # COMMISSION CALCULATION
    # ========================================================
    # Commission is calculated from printing_cost.
    #
    # Business logic:
    # Direct commission = 10% of printing cost
    # Parent commission = 5% of direct commission
    # Grandparent commission = 2.5% of direct commission
    #
    # Final direct commission =
    # Direct commission - parent commission - grandparent commission

    commission = calculate_commission(
        printing_cost=order_data.printing_cost,
        has_parent=parent_agent is not None,
        has_grandparent=grandparent_agent is not None,
    )

    # ========================================================
    # GENERATE JOB / ORDER ID
    # ========================================================

    order_id = generate_order_id(db)

    # ========================================================
    # CREATE JOB / ORDER OBJECT
    # ========================================================

    order = Order(
        order_id=order_id,

        # Basic job details
        customer_name=order_data.customer_name,
        product_name=order_data.product_name,

        quantity=order_data.quantity,
        unit_price=order_data.unit_price,
        total_amount=total_amount,
        printing_cost=order_data.printing_cost,

        # Commission chain member ids
        direct_agent_id=direct_agent.id,
        parent_agent_id=parent_agent.id if parent_agent else None,
        grandparent_agent_id=grandparent_agent.id if grandparent_agent else None,

        # Commission values
        direct_agent_commission=commission["total_direct_commission"],
        parent_commission=commission["parent_commission"],
        grandparent_commission=commission["grandparent_commission"],
        final_direct_agent_commission=commission["final_direct_agent_commission"],

        # Job status and dates
        status="Pending",
        delivery_date=order_data.delivery_date,
        created_date=str(date.today()),

        # Requirement costing
        paper_type=order_data.paper_type,
        paper_amount=paper_amount,

        plate_type=order_data.plate_type,
        plate_amount=plate_amount,

        printing_type=order_data.printing_type,
        printing_amount=printing_amount,

        lamination_type=order_data.lamination_type,
        lamination_amount=lamination_amount,

        binding_type=order_data.binding_type,
        binding_amount=binding_amount,

        requirement_total_amount=requirement_total_amount,
    )

    # ========================================================
    # UPDATE MEMBER BUSINESS TOTALS
    # ========================================================
    # Direct member:
    # - total_orders increases by 1
    # - total_commission gets final direct commission
    # - printing_revenue gets printing cost
    #
    # Parent and grandparent:
    # - total_commission gets their commission shares

    direct_agent.total_orders += 1
    direct_agent.total_commission += commission["final_direct_agent_commission"]
    direct_agent.printing_revenue += order_data.printing_cost

    if parent_agent:
        parent_agent.total_commission += commission["parent_commission"]

    if grandparent_agent:
        grandparent_agent.total_commission += commission["grandparent_commission"]

    # ========================================================
    # SAVE ORDER FIRST
    # ========================================================
    # db.flush() saves order temporarily and gives order.id.
    # We need order.id for commission_payments.order_db_id.
    #
    # Final commit happens after payment records are created.

    db.add(order)
    db.flush()

    # ========================================================
    # CREATE COMMISSION PAYMENT RECORDS
    # ========================================================
    # Correct payment architecture:
    # Payment module means company pays commission to members.
    #
    # One job can create:
    # 1. Direct Member payment
    # 2. Parent Member payment
    # 3. Grandparent Member payment

    payment_extra_count = 0

    # Direct member payment
    direct_commission_amount = float(
        commission["final_direct_agent_commission"] or 0
    )

    if direct_commission_amount > 0:
        create_commission_payment(
            db=db,
            payment_id=generate_payment_id(db, payment_extra_count),
            order=order,
            agent=direct_agent,
            agent_role="Direct Member",
            commission_amount=direct_commission_amount,
        )

        payment_extra_count += 1

    # Parent member payment
    parent_commission_amount = float(
        commission["parent_commission"] or 0
    )

    if parent_agent and parent_commission_amount > 0:
        create_commission_payment(
            db=db,
            payment_id=generate_payment_id(db, payment_extra_count),
            order=order,
            agent=parent_agent,
            agent_role="Parent Member",
            commission_amount=parent_commission_amount,
        )

        payment_extra_count += 1

    # Grandparent member payment
    grandparent_commission_amount = float(
        commission["grandparent_commission"] or 0
    )

    if grandparent_agent and grandparent_commission_amount > 0:
        create_commission_payment(
            db=db,
            payment_id=generate_payment_id(db, payment_extra_count),
            order=order,
            agent=grandparent_agent,
            agent_role="Grandparent Member",
            commission_amount=grandparent_commission_amount,
        )

        payment_extra_count += 1

    # ========================================================
    # FINAL SAVE
    # ========================================================

    db.commit()
    db.refresh(order)

    if is_agent:
        notification = Notification(
            user_id=None,
            title="New Costing Request",
            message=f"Agent {current_user.name} created job {order.order_id} ({order.product_name}). Please enter costing.",
            is_read=False,
            created_date=str(date.today()),
            order_id=order.id,
        )
        db.add(notification)
        db.commit()

    return order


# ============================================================
# UPDATE JOB / ORDER STATUS
# ============================================================
# URL:
# PUT /api/orders/{order_id}/status
#
# Permission:
# super_admin, admin
#
# Request body:
# {
#   "status": "Running"
# }
#
# Allowed statuses:
# Pending
# Running
# Completed

@router.put(
    "/{order_id}/status",
    response_model=OrderResponse,
    dependencies=[
        Depends(require_roles(["super_admin", "admin"]))
    ],
)
def update_order_status(
    order_id: int,
    status_data: dict = Body(...),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    new_status = status_data.get("status")

    allowed_status = ["Pending", "Running", "Completed"]

    if new_status not in allowed_status:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Allowed values are Pending, Running, Completed",
        )

    order.status = new_status

    db.commit()
    db.refresh(order)

    return order


# ============================================================
# DELETE JOB / ORDER
# ============================================================
# URL:
# DELETE /api/orders/{order_id}
#
# Permission:
# super_admin, admin

@router.delete(
    "/{order_id}",
    dependencies=[
        Depends(require_roles(["super_admin", "admin"]))
    ],
)
def delete_order(
    order_id: int,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    # Revert Agent totals
    direct_agent = db.query(Agent).filter(Agent.id == order.direct_agent_id).first()
    if direct_agent:
        direct_agent.total_orders = max(0, direct_agent.total_orders - 1)
        direct_agent.total_commission = max(0.0, direct_agent.total_commission - (order.final_direct_agent_commission or 0))
        direct_agent.printing_revenue = max(0.0, direct_agent.printing_revenue - (order.printing_cost or 0))

    if order.parent_agent_id:
        parent_agent = db.query(Agent).filter(Agent.id == order.parent_agent_id).first()
        if parent_agent:
            parent_agent.total_commission = max(0.0, parent_agent.total_commission - (order.parent_commission or 0))

    if order.grandparent_agent_id:
        grandparent_agent = db.query(Agent).filter(Agent.id == order.grandparent_agent_id).first()
        if grandparent_agent:
            grandparent_agent.total_commission = max(0.0, grandparent_agent.total_commission - (order.grandparent_commission or 0))

    # Delete commission payment records
    db.query(CommissionPayment).filter(CommissionPayment.order_db_id == order.id).delete(synchronize_session=False)

    # Delete order
    db.delete(order)
    db.commit()

    return {"message": "Job and associated payments deleted successfully", "deleted_order_id": order_id}


# ============================================================
# COSTING RECALCULATION & PAYMENTS HELPERS
# ============================================================

from app.routes.payments import calculate_payment_status

def update_or_create_commission_payment(
    db: Session,
    order: Order,
    agent: Agent,
    agent_role: str,
    commission_amount: float,
    extra_count: int,
):
    payment = (
        db.query(CommissionPayment)
        .filter(
            CommissionPayment.order_db_id == order.id,
            CommissionPayment.agent_id == agent.id,
            CommissionPayment.agent_role == agent_role,
        )
        .first()
    )

    if payment:
        payment.commission_amount = commission_amount
        payment.pending_amount = commission_amount - payment.paid_amount
        payment.payment_status = calculate_payment_status(
            commission_amount=commission_amount,
            paid_amount=payment.paid_amount,
        )
        payment.updated_date = str(date.today())
    elif commission_amount > 0:
        create_commission_payment(
            db=db,
            payment_id=generate_payment_id(db, extra_count),
            order=order,
            agent=agent,
            agent_role=agent_role,
            commission_amount=commission_amount,
        )
        return True
    return False


# ============================================================
# UPDATE JOB / ORDER COSTING
# ============================================================
# URL:
# PUT /api/orders/{order_id}/costing

@router.put(
    "/{order_id}/costing",
    response_model=OrderResponse,
    dependencies=[Depends(require_roles(["super_admin", "admin"]))],
)
def update_order_costing(
    order_id: int,
    costing_data: OrderCostingUpdate,
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    # 1. Revert old commission from Agent totals
    direct_agent = db.query(Agent).filter(Agent.id == order.direct_agent_id).first()
    if direct_agent:
        direct_agent.total_commission = max(
            0.0,
            direct_agent.total_commission - (order.final_direct_agent_commission or 0)
        )
        direct_agent.printing_revenue = max(
            0.0,
            direct_agent.printing_revenue - (order.printing_cost or 0)
        )

    parent_agent = None
    if order.parent_agent_id:
        parent_agent = db.query(Agent).filter(Agent.id == order.parent_agent_id).first()
        if parent_agent:
            parent_agent.total_commission = max(
                0.0,
                parent_agent.total_commission - (order.parent_commission or 0)
            )

    grandparent_agent = None
    if order.grandparent_agent_id:
        grandparent_agent = db.query(Agent).filter(Agent.id == order.grandparent_agent_id).first()
        if grandparent_agent:
            grandparent_agent.total_commission = max(
                0.0,
                grandparent_agent.total_commission - (order.grandparent_commission or 0)
            )

    # 2. Update costing amounts
    order.paper_amount = float(costing_data.paper_amount or 0)
    order.plate_amount = float(costing_data.plate_amount or 0)
    order.printing_amount = float(costing_data.printing_amount or 0)
    order.lamination_amount = float(costing_data.lamination_amount or 0)
    order.binding_amount = float(costing_data.binding_amount or 0)

    # Recalculate totals
    requirement_total_amount = (
        order.paper_amount
        + order.plate_amount
        + order.printing_amount
        + order.lamination_amount
        + order.binding_amount
    )
    order.requirement_total_amount = requirement_total_amount
    order.total_amount = requirement_total_amount
    order.printing_cost = requirement_total_amount

    if order.quantity > 0:
        order.unit_price = requirement_total_amount / order.quantity
    else:
        order.unit_price = 0

    # 3. Recalculate commission
    commission = calculate_commission(
        printing_cost=order.printing_cost,
        has_parent=parent_agent is not None,
        has_grandparent=grandparent_agent is not None,
    )

    # Update order commissions
    order.direct_agent_commission = commission["total_direct_commission"]
    order.parent_commission = commission["parent_commission"]
    order.grandparent_commission = commission["grandparent_commission"]
    order.final_direct_agent_commission = commission["final_direct_agent_commission"]

    # 4. Add new commission to Agent totals
    if direct_agent:
        direct_agent.total_commission += order.final_direct_agent_commission
        direct_agent.printing_revenue += order.printing_cost

    if parent_agent:
        parent_agent.total_commission += order.parent_commission

    if grandparent_agent:
        grandparent_agent.total_commission += order.grandparent_commission

    # 5. Create or update payment records
    payment_extra_count = 0

    if direct_agent:
        created = update_or_create_commission_payment(
            db=db,
            order=order,
            agent=direct_agent,
            agent_role="Direct Member",
            commission_amount=order.final_direct_agent_commission,
            extra_count=payment_extra_count,
        )
        if created:
            payment_extra_count += 1

    if parent_agent:
        created = update_or_create_commission_payment(
            db=db,
            order=order,
            agent=parent_agent,
            agent_role="Parent Member",
            commission_amount=order.parent_commission,
            extra_count=payment_extra_count,
        )
        if created:
            payment_extra_count += 1

    if grandparent_agent:
        created = update_or_create_commission_payment(
            db=db,
            order=order,
            agent=grandparent_agent,
            agent_role="Grandparent Member",
            commission_amount=order.grandparent_commission,
            extra_count=payment_extra_count,
        )
        if created:
            payment_extra_count += 1

    # 6. Auto-mark any corresponding notifications for this order as read
    db.query(Notification).filter(
        Notification.order_id == order.id,
        Notification.is_read == False
    ).update({Notification.is_read: True}, synchronize_session=False)

    db.commit()
    db.refresh(order)

    return order


@router.put(
    "/{order_id}/quantity",
    response_model=OrderResponse,
    dependencies=[Depends(require_roles(["super_admin"]))],
)
def update_order_quantity(
    order_id: int,
    quantity: int = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than 0",
        )

    order.quantity = quantity
    if quantity > 0:
        order.unit_price = (order.requirement_total_amount or 0) / quantity
    else:
        order.unit_price = 0

    db.commit()
    db.refresh(order)
    return order

