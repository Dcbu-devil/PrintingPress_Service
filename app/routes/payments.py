from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent, Order, CommissionPayment
from app.schemas import CommissionPaymentResponse, CommissionPaymentUpdate


router = APIRouter(prefix="/api/payments", tags=["Payments"])


# =========================
# HELPER FUNCTIONS
# =========================

def calculate_payment_status(commission_amount: float, paid_amount: float):
    commission_amount = float(commission_amount or 0)
    paid_amount = float(paid_amount or 0)

    if paid_amount <= 0:
        return "Pending"

    if paid_amount < commission_amount:
        return "Partial"

    return "Paid"


def generate_payment_id(db: Session, extra_count: int = 0):
    payment_count = db.query(CommissionPayment).count()
    return f"PAY-{1001 + payment_count + extra_count}"


def create_payment_if_not_exists(
    db: Session,
    order: Order,
    agent: Agent,
    agent_role: str,
    commission_amount: float,
    extra_count: int,
):
    commission_amount = float(commission_amount or 0)

    if commission_amount <= 0:
        return False

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

        order_db_id=order.id,
        order_id=order.order_id,

        agent_id=agent.id,
        agent_name=agent.name,
        agent_role=agent_role,

        commission_amount=commission_amount,
        paid_amount=0,
        pending_amount=commission_amount,

        payment_status="Pending",
        payment_date=None,
        payment_method=None,

        created_date=str(date.today()),
        updated_date=str(date.today()),
    )

    db.add(payment)

    return True


# =========================
# GET ALL COMMISSION PAYMENTS
# =========================

@router.get("/", response_model=list[CommissionPaymentResponse])
def get_payments(db: Session = Depends(get_db)):
    payments = (
        db.query(CommissionPayment)
        .order_by(CommissionPayment.id.desc())
        .all()
    )

    return payments


# =========================
# BACKFILL OLD JOBS
# =========================
# This fixes old jobs created before commission_payments table existed.
#
# Run this once from Swagger:
# POST /api/payments/backfill-missing

@router.post("/backfill-missing")
def backfill_missing_commission_payments(db: Session = Depends(get_db)):
    orders = db.query(Order).order_by(Order.id.asc()).all()

    created_count = 0
    extra_count = 0

    for order in orders:
        # Direct member payment
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

        # Parent member payment
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

        # Grandparent member payment
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


# =========================
# UPDATE COMMISSION PAYMENT
# =========================

@router.put("/{payment_id}/pay", response_model=CommissionPaymentResponse)
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
            detail="Payment record not found"
        )

    commission_amount = float(payment.commission_amount or 0)
    paid_amount = float(payment_data.paid_amount or 0)

    if paid_amount < 0:
        raise HTTPException(
            status_code=400,
            detail="Paid amount cannot be negative"
        )

    if paid_amount > commission_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Paid amount cannot exceed commission amount ₹{commission_amount}"
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


# =========================
# REVERT COMMISSION PAYMENT
# =========================

@router.put("/{payment_id}/revert", response_model=CommissionPaymentResponse)
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
            detail="Payment record not found"
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


# =========================
# GET SINGLE PAYMENT RECORD
# =========================

@router.get("/{payment_id}", response_model=CommissionPaymentResponse)
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
            detail="Payment record not found"
        )

    return payment