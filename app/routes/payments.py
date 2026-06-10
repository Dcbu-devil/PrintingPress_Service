from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent, Order, CommissionPayment
from app.schemas import CommissionPaymentResponse, CommissionPaymentUpdate
from app.auth import require_roles


# ============================================================
# PAYMENTS ROUTER
# ============================================================
# Purpose:
# This file handles company-to-member commission payments.
#
# Payment module meaning:
# Company pays commission to members/agents.
#
# Example:
# Job ORD-1001 can create payment records like:
#
# PAY-1001 -> Direct Member       -> ₹925
# PAY-1002 -> Parent Member       -> ₹50
# PAY-1003 -> Grandparent Member  -> ₹25
#
# Important:
# This route is now protected with JWT role permissions.
#
# Permission rules:
# 1. super_admin and admin can view payments.
# 2. Only super_admin can pay commission.
# 3. Only super_admin can revert payment.
# 4. Only super_admin can run old-job backfill.

router = APIRouter(
    prefix="/api/payments",
    tags=["Payments"],
)


# ============================================================
# HELPER: CALCULATE PAYMENT STATUS
# ============================================================
# Purpose:
# Decides payment status based on paid amount.
#
# Rules:
# paid_amount <= 0
#   -> Pending
#
# paid_amount > 0 and paid_amount < commission_amount
#   -> Partial
#
# paid_amount == commission_amount
#   -> Paid

def calculate_payment_status(
    commission_amount: float,
    paid_amount: float,
):
    commission_amount = float(commission_amount or 0)
    paid_amount = float(paid_amount or 0)

    if paid_amount <= 0:
        return "Pending"

    if paid_amount < commission_amount:
        return "Partial"

    return "Paid"


# ============================================================
# HELPER: GENERATE PAYMENT ID
# ============================================================
# Purpose:
# Generates public payment id like:
#
# PAY-1001
# PAY-1002
# PAY-1003
#
# Note:
# This is okay for current MVP.
# Later for production with many users, improve this using:
# - database sequence
# - UUID
# - safer retry logic

def generate_payment_id(
    db: Session,
    extra_count: int = 0,
):
    payment_count = db.query(CommissionPayment).count()
    return f"PAY-{1001 + payment_count + extra_count}"


# ============================================================
# HELPER: CREATE PAYMENT IF NOT EXISTS
# ============================================================
# Purpose:
# Used by backfill API.
#
# This creates missing payment records for old jobs that were created
# before the commission_payments table/module existed.
#
# It prevents duplicate payment records by checking:
# - order_db_id
# - agent_id
# - agent_role

def create_payment_if_not_exists(
    db: Session,
    order: Order,
    agent: Agent,
    agent_role: str,
    commission_amount: float,
    extra_count: int,
):
    commission_amount = float(commission_amount or 0)

    # Do not create zero or negative commission payment.
    if commission_amount <= 0:
        return False

    # Check if this payment record already exists.
    existing_payment = (
        db.query(CommissionPayment)
        .filter(
            CommissionPayment.order_db_id == order.id,
            CommissionPayment.agent_id == agent.id,
            CommissionPayment.agent_role == agent_role,
        )
        .first()
    )

    if existing_payment:
        return False

    payment = CommissionPayment(
        payment_id=generate_payment_id(db, extra_count),

        # Job/order reference
        order_db_id=order.id,
        order_id=order.order_id,

        # Member/agent receiving commission
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

    return True


# ============================================================
# GET ALL COMMISSION PAYMENTS
# ============================================================
# URL:
# GET /api/payments/
#
# Permission:
# super_admin, admin
#
# Purpose:
# Returns all commission payment records.
#
# Used by:
# Frontend Payments page.

@router.get(
    "/",
    response_model=list[CommissionPaymentResponse],
    dependencies=[
        Depends(require_roles(["super_admin", "admin"]))
    ],
)
def get_payments(
    db: Session = Depends(get_db),
):
    payments = (
        db.query(CommissionPayment)
        .order_by(CommissionPayment.id.desc())
        .all()
    )

    return payments


# ============================================================
# BACKFILL OLD JOBS
# ============================================================
# URL:
# POST /api/payments/backfill-missing
#
# Permission:
# super_admin only
#
# Purpose:
# This fixes old jobs created before commission_payments table existed.
#
# Use case:
# You already have jobs/orders in orders table,
# but payment page shows no commission rows.
#
# This API reads old jobs and creates missing payment records.

@router.post(
    "/backfill-missing",
    dependencies=[
        Depends(require_roles(["super_admin"]))
    ],
)
def backfill_missing_commission_payments(
    db: Session = Depends(get_db),
):
    orders = db.query(Order).order_by(Order.id.asc()).all()

    created_count = 0
    extra_count = 0

    for order in orders:
        # ====================================================
        # DIRECT MEMBER PAYMENT
        # ====================================================

        if order.direct_agent_id:
            direct_agent = (
                db.query(Agent)
                .filter(Agent.id == order.direct_agent_id)
                .first()
            )

            if direct_agent:
                created = create_payment_if_not_exists(
                    db=db,
                    order=order,
                    agent=direct_agent,
                    agent_role="Direct Member",
                    commission_amount=order.final_direct_agent_commission,
                    extra_count=extra_count,
                )

                if created:
                    created_count += 1
                    extra_count += 1

        # ====================================================
        # PARENT MEMBER PAYMENT
        # ====================================================

        if order.parent_agent_id and float(order.parent_commission or 0) > 0:
            parent_agent = (
                db.query(Agent)
                .filter(Agent.id == order.parent_agent_id)
                .first()
            )

            if parent_agent:
                created = create_payment_if_not_exists(
                    db=db,
                    order=order,
                    agent=parent_agent,
                    agent_role="Parent Member",
                    commission_amount=order.parent_commission,
                    extra_count=extra_count,
                )

                if created:
                    created_count += 1
                    extra_count += 1

        # ====================================================
        # GRANDPARENT MEMBER PAYMENT
        # ====================================================

        if (
            order.grandparent_agent_id
            and float(order.grandparent_commission or 0) > 0
        ):
            grandparent_agent = (
                db.query(Agent)
                .filter(Agent.id == order.grandparent_agent_id)
                .first()
            )

            if grandparent_agent:
                created = create_payment_if_not_exists(
                    db=db,
                    order=order,
                    agent=grandparent_agent,
                    agent_role="Grandparent Member",
                    commission_amount=order.grandparent_commission,
                    extra_count=extra_count,
                )

                if created:
                    created_count += 1
                    extra_count += 1

    db.commit()

    return {
        "success": True,
        "message": "Missing commission payment records created successfully",
        "created_records": created_count,
    }


# ============================================================
# UPDATE COMMISSION PAYMENT
# ============================================================
# URL:
# PUT /api/payments/{payment_id}/pay
#
# Permission:
# super_admin only
#
# Request body:
# {
#   "paid_amount": 500,
#   "payment_method": "Company Payment"
# }
#
# Rules:
# paid_amount cannot be negative.
# paid_amount cannot exceed commission_amount.
#
# Status update:
# paid_amount = 0
#   -> Pending
#
# paid_amount < commission_amount
#   -> Partial
#
# paid_amount == commission_amount
#   -> Paid

@router.put(
    "/{payment_id}/pay",
    response_model=CommissionPaymentResponse,
    dependencies=[
        Depends(require_roles(["super_admin"]))
    ],
)
def update_payment(
    payment_id: int,
    payment_data: CommissionPaymentUpdate,
    db: Session = Depends(get_db),
):
    payment = (
        db.query(CommissionPayment)
        .filter(CommissionPayment.id == payment_id)
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment record not found",
        )

    commission_amount = float(payment.commission_amount or 0)
    paid_amount = float(payment_data.paid_amount or 0)

    # Prevent negative payment.
    if paid_amount < 0:
        raise HTTPException(
            status_code=400,
            detail="Paid amount cannot be negative",
        )

    # Prevent overpayment.
    if paid_amount > commission_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Paid amount cannot exceed commission amount ₹{commission_amount}",
        )

    pending_amount = commission_amount - paid_amount

    payment.paid_amount = paid_amount
    payment.pending_amount = pending_amount
    payment.payment_status = calculate_payment_status(
        commission_amount=commission_amount,
        paid_amount=paid_amount,
    )

    if paid_amount > 0:
        payment.payment_date = str(date.today())
        payment.payment_method = payment_data.payment_method or "Company Payment"
    else:
        payment.payment_date = None
        payment.payment_method = None

    payment.updated_date = str(date.today())

    db.commit()
    db.refresh(payment)

    return payment


# ============================================================
# REVERT COMMISSION PAYMENT
# ============================================================
# URL:
# PUT /api/payments/{payment_id}/revert
#
# Permission:
# super_admin only
#
# Purpose:
# Resets a payment record back to unpaid state.
#
# It sets:
# paid_amount = 0
# pending_amount = commission_amount
# payment_status = Pending
# payment_date = None
# payment_method = None

@router.put(
    "/{payment_id}/revert",
    response_model=CommissionPaymentResponse,
    dependencies=[
        Depends(require_roles(["super_admin"]))
    ],
)
def revert_payment(
    payment_id: int,
    db: Session = Depends(get_db),
):
    payment = (
        db.query(CommissionPayment)
        .filter(CommissionPayment.id == payment_id)
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment record not found",
        )

    commission_amount = float(payment.commission_amount or 0)

    payment.paid_amount = 0
    payment.pending_amount = commission_amount
    payment.payment_status = "Pending"
    payment.payment_date = None
    payment.payment_method = None
    payment.updated_date = str(date.today())

    db.commit()
    db.refresh(payment)

    return payment


# ============================================================
# GET SINGLE PAYMENT RECORD
# ============================================================
# URL:
# GET /api/payments/{payment_id}
#
# Permission:
# super_admin, admin
#
# Purpose:
# Returns one commission payment record by database ID.

@router.get(
    "/{payment_id}",
    response_model=CommissionPaymentResponse,
    dependencies=[
        Depends(require_roles(["super_admin", "admin"]))
    ],
)
def get_single_payment(
    payment_id: int,
    db: Session = Depends(get_db),
):
    payment = (
        db.query(CommissionPayment)
        .filter(CommissionPayment.id == payment_id)
        .first()
    )

    if not payment:
        raise HTTPException(
            status_code=404,
            detail="Payment record not found",
        )

    return payment