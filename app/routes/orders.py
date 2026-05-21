from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent, Order
from app.schemas import OrderCreate, OrderResponse
from app.commission import calculate_commission

router = APIRouter(prefix="/api/orders", tags=["Orders"])


@router.get("/", response_model=list[OrderResponse])
def get_orders(db: Session = Depends(get_db)):
    return db.query(Order).order_by(Order.id.desc()).all()


@router.post("/", response_model=OrderResponse)
def create_order(order_data: OrderCreate, db: Session = Depends(get_db)):
    direct_agent = (
        db.query(Agent)
        .filter(Agent.id == order_data.direct_agent_id)
        .first()
    )

    if not direct_agent:
        raise HTTPException(status_code=404, detail="Direct agent not found")

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

    total_amount = order_data.quantity * order_data.unit_price

    commission = calculate_commission(
        printing_cost=order_data.printing_cost,
        has_parent=parent_agent is not None,
        has_grandparent=grandparent_agent is not None,
    )

    order_count = db.query(Order).count() + 1
    order_id = f"ORD-{1000 + order_count}"

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
    )

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