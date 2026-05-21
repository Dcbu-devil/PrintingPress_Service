from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    name = Column(String, nullable=False, index=True)
    email = Column(String, unique=True, index=True)
    phone = Column(String)
    address = Column(String)

    parent_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)

    total_orders = Column(Integer, default=0)
    total_commission = Column(Float, default=0)
    printing_revenue = Column(Float, default=0)

    status = Column(String, default="Active")
    joined_date = Column(String)

    parent = relationship("Agent", remote_side=[id])


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)

    order_id = Column(String, unique=True, index=True)
    customer_name = Column(String, nullable=False)
    product_name = Column(String, nullable=False)

    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    printing_cost = Column(Float, nullable=False)

    direct_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    parent_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    grandparent_agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)

    direct_agent_commission = Column(Float, default=0)
    parent_commission = Column(Float, default=0)
    grandparent_commission = Column(Float, default=0)
    final_direct_agent_commission = Column(Float, default=0)

    status = Column(String, default="Pending")
    delivery_date = Column(String)
    created_date = Column(String)

    direct_agent = relationship("Agent", foreign_keys=[direct_agent_id])