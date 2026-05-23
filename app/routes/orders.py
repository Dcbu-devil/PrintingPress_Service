from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent, Order
from app.schemas import OrderCreate, OrderResponse
from app.commission import calculate_commission

router = APIRouter(prefix="/api/orders", tags=["Orders"])


# =========================
# GET ALL JOBS / ORDERS
# =========================

@router.get("/", response_model=list[OrderResponse])
def get_orders(db: Session = Depends(get_db)):
    return db.query(Order).order_by(Order.id.desc()).all()


# =========================
# CREATE JOB / ORDER
# =========================

@router.post("/", response_model=OrderResponse)
def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    # =========================
    # FIND DIRECT MEMBER / AGENT
    # =========================

    direct_agent = (
        db.query(Agent)
        .filter(Agent.id == order_data.direct_agent_id)
        .first()
    )

    if not direct_agent:
        raise HTTPException(
            status_code=404,
            detail="Direct member not found"
        )

    # =========================
    # FIND PARENT AND GRANDPARENT
    # =========================

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

    # =========================
    # REQUIREMENT TOTAL CALCULATION
    # =========================
    # Total amount = Paper + Plate + Printing + Lamination + Binding

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

    total_amount = requirement_total_amount

    # =========================
    # COMMISSION CALCULATION
    # =========================
    # Commission is still calculated from printing_cost.

    commission = calculate_commission(
        printing_cost=order_data.printing_cost,
        has_parent=parent_agent is not None,
        has_grandparent=grandparent_agent is not None,
    )

    # =========================
    # GENERATE JOB / ORDER ID
    # =========================

    order_count = db.query(Order).count() + 1
    order_id = f"ORD-{1000 + order_count}"

    # =========================
    # CREATE JOB / ORDER OBJECT
    # =========================

    order = Order(
        order_id=order_id,

        customer_name=order_data.customer_name,
        product_name=order_data.product_name,

        quantity=order_data.quantity,
        unit_price=order_data.unit_price,
        total_amount=total_amount,
        printing_cost=order_data.printing_cost,

        direct_agent_id=direct_agent.id,
        parent_agent_id=parent_agent.id if parent_agent else None,
        grandparent_agent_id=grandparent_agent.id if grandparent_agent else None,

        direct_agent_commission=commission["total_direct_commission"],
        parent_commission=commission["parent_commission"],
        grandparent_commission=commission["grandparent_commission"],
        final_direct_agent_commission=commission["final_direct_agent_commission"],

        status="Pending",
        delivery_date=order_data.delivery_date,
        created_date=str(date.today()),

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

    # =========================
    # UPDATE DIRECT MEMBER TOTALS
    # =========================

    direct_agent.total_orders += 1
    direct_agent.total_commission += commission["final_direct_agent_commission"]
    direct_agent.printing_revenue += order_data.printing_cost

    if parent_agent:
        parent_agent.total_commission += commission["parent_commission"]

    if grandparent_agent:
        grandparent_agent.total_commission += commission["grandparent_commission"]

    db.add(order)
    db.commit()
    db.refresh(order)

    return order


# =========================
# UPDATE JOB / ORDER STATUS
# =========================
# Frontend dropdown will call:
# PUT /api/orders/{order_id}/status

@router.put("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_data: dict,
    db: Session = Depends(get_db)
):
    order = db.query(Order).filter(Order.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    new_status = status_data.get("status")

    allowed_status = ["Pending", "Running", "Completed"]

    if new_status not in allowed_status:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Allowed values are Pending, Running, Completed"
        )

    order.status = new_status

    db.commit()
    db.refresh(order)

    return order