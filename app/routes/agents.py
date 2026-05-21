from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent
from app.schemas import AgentCreate, AgentUpdate, AgentResponse

router = APIRouter(prefix="/api/agents", tags=["Agents"])


# =========================
# GENERATE SEQUENTIAL CODE
# =========================

def generate_agent_code(db: Session):
    last_agent = db.query(Agent).order_by(Agent.id.desc()).first()

    if not last_agent:
        return "AG001"

    next_number = last_agent.id + 1
    new_code = f"AG{next_number:03d}"

    existing_code = db.query(Agent).filter(Agent.code == new_code).first()

    while existing_code:
        next_number += 1
        new_code = f"AG{next_number:03d}"
        existing_code = db.query(Agent).filter(Agent.code == new_code).first()

    return new_code


# =========================
# GET ALL AGENTS / MEMBERS
# =========================

@router.get("/", response_model=list[AgentResponse])
def get_agents(db: Session = Depends(get_db)):
    return db.query(Agent).order_by(Agent.id.asc()).all()


# =========================
# CREATE AGENT / MEMBER
# =========================

@router.post("/", response_model=AgentResponse)
def create_agent(agent_data: AgentCreate, db: Session = Depends(get_db)):
    existing_email = db.query(Agent).filter(
        Agent.email == agent_data.email
    ).first()

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Member email already exists"
        )

    if agent_data.parent_agent_id:
        parent = db.query(Agent).filter(
            Agent.id == agent_data.parent_agent_id
        ).first()

        if not parent:
            raise HTTPException(
                status_code=404,
                detail="Parent member not found"
            )

    agent_code = generate_agent_code(db)

    agent_payload = agent_data.model_dump()
    agent_payload.pop("code", None)

    agent = Agent(
        code=agent_code,
        **agent_payload
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return agent


# =========================
# HIERARCHY TREE
# IMPORTANT:
# Keep this BEFORE /{agent_id}
# =========================

@router.get("/hierarchy/tree")
def get_agent_hierarchy(db: Session = Depends(get_db)):
    agents = db.query(Agent).order_by(Agent.id.asc()).all()

    agent_map = {}

    for agent in agents:
        agent_map[agent.id] = {
            "id": agent.id,
            "code": agent.code,
            "name": agent.name,
            "email": agent.email,
            "phone": agent.phone,
            "address": agent.address,
            "parent_agent_id": agent.parent_agent_id,
            "total_orders": agent.total_orders,
            "total_commission": agent.total_commission,
            "printing_revenue": agent.printing_revenue,
            "status": agent.status,
            "joined_date": agent.joined_date,
            "children": [],
        }

    root_agents = []

    for agent in agents:
        current_agent = agent_map[agent.id]

        if agent.parent_agent_id and agent.parent_agent_id in agent_map:
            agent_map[agent.parent_agent_id]["children"].append(current_agent)
        else:
            root_agents.append(current_agent)

    return root_agents


# =========================
# GET SINGLE AGENT / MEMBER
# =========================

@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )

    return agent


# =========================
# UPDATE AGENT / MEMBER
# =========================

@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )

    existing_email = db.query(Agent).filter(
        Agent.email == agent_data.email,
        Agent.id != agent_id
    ).first()

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Another member already uses this email"
        )

    if agent_data.parent_agent_id:
        if agent_data.parent_agent_id == agent_id:
            raise HTTPException(
                status_code=400,
                detail="Member cannot be parent of itself"
            )

        parent = db.query(Agent).filter(
            Agent.id == agent_data.parent_agent_id
        ).first()

        if not parent:
            raise HTTPException(
                status_code=404,
                detail="Parent member not found"
            )

    agent.name = agent_data.name
    agent.email = agent_data.email
    agent.phone = agent_data.phone
    agent.address = agent_data.address
    agent.parent_agent_id = agent_data.parent_agent_id
    agent.status = agent_data.status
    agent.joined_date = agent_data.joined_date

    db.commit()
    db.refresh(agent)

    return agent


# =========================
# DELETE AGENT / MEMBER
# =========================

@router.delete("/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )

    child_count = db.query(Agent).filter(
        Agent.parent_agent_id == agent_id
    ).count()

    if child_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete this member because connected child members exist. First change or delete child members."
        )

    db.delete(agent)
    db.commit()

    return {
        "message": "Member deleted successfully",
        "deleted_member_id": agent_id
    }