from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent, User, Role, Order, CommissionPayment
from app.schemas import AgentCreate, AgentUpdate, AgentResponse
from app.auth import require_roles, get_password_hash, get_current_user
from app.utils import generate_temp_password


# ============================================================
# AGENTS / MEMBERS ROUTER
# ============================================================
# Purpose:
# This file manages members/agents.
#
# Frontend name:
# Members
#
# Backend model/table name:
# Agent
#
# When Admin/Super Admin creates a member,
# backend automatically creates login user:
#
# Login email = member email
# First password = password
# Role = agent
# must_reset_password = True
# agent_id = newly created member id

router = APIRouter(
    prefix="/api/agents",
    tags=["Agents"],
)


# ============================================================
# HELPER: GENERATE SEQUENTIAL MEMBER CODE
# ============================================================

def generate_agent_code(db: Session):
    last_agent = db.query(Agent).order_by(Agent.id.desc()).first()

    if not last_agent or not last_agent.code:
        return "AG001"

    # Extract numeric part from last code for reliable sequencing
    # even if agents have been deleted and IDs have gaps.
    try:
        last_num = int(last_agent.code.replace("AG", ""))
        next_number = last_num + 1
    except ValueError:
        next_number = last_agent.id + 1

    new_code = f"AG{next_number:03d}"

    # Ensure uniqueness
    while db.query(Agent).filter(Agent.code == new_code).first():
        next_number += 1
        new_code = f"AG{next_number:03d}"

    return new_code


# ============================================================
# HELPER: CHECK CIRCULAR HIERARCHY
# ============================================================

def is_circular_parent(
    db: Session,
    agent_id: int,
    new_parent_id: int,
):
    current_parent_id = new_parent_id

    while current_parent_id:
        if current_parent_id == agent_id:
            return True

        parent = (
            db.query(Agent)
            .filter(Agent.id == current_parent_id)
            .first()
        )

        if not parent:
            return False

        current_parent_id = parent.parent_agent_id

    return False


# ============================================================
# HELPER: GET OR CREATE AGENT ROLE
# ============================================================

def get_or_create_agent_role(db: Session):
    agent_role = (
        db.query(Role)
        .filter(Role.name == "agent")
        .first()
    )

    if agent_role:
        return agent_role

    agent_role = Role(
        name="agent",
        description="Member / sales person",
    )

    db.add(agent_role)
    db.flush()

    return agent_role


# ============================================================
# HELPER: AUTO CREATE LOGIN USER FOR MEMBER / AGENT
# ============================================================

def create_login_user_for_agent(
    db: Session,
    agent: Agent,
    temp_password: str,
):
    existing_user = (
        db.query(User)
        .filter(User.email == agent.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Login user already exists with this email",
        )

    agent_role = get_or_create_agent_role(db)

    new_user = User(
        name=agent.name,
        email=agent.email,
        hashed_password=get_password_hash(temp_password),
        role_id=agent_role.id,
        agent_id=agent.id,
        status="Active",
        must_reset_password=False,
        created_date=agent.joined_date,
    )

    db.add(new_user)
    db.flush()

    return new_user


# ============================================================
# GET ALL AGENTS / MEMBERS
# ============================================================
# URL:
# GET /api/agents/

@router.get(
    "/",
    response_model=list[AgentResponse],
    dependencies=[
        Depends(require_roles(["super_admin", "admin"]))
    ],
)
def get_agents(
    db: Session = Depends(get_db),
):
    return db.query(Agent).order_by(Agent.id.asc()).all()


# ============================================================
# CREATE AGENT / MEMBER
# ============================================================
# URL:
# POST /api/agents/
#
# Important:
# This creates:
# 1. Agent/member row
# 2. Login user row
#
# Login:
# Email = member email
# First password = password
# must_reset_password = True

@router.post(
    "/",
    dependencies=[
        Depends(require_roles(["super_admin", "admin", "agent"]))
    ],
)
def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role.name == "agent":
        if not current_user.agent_id:
            raise HTTPException(
                status_code=400,
                detail="User has no connected member profile",
            )
        agent_data.parent_agent_id = current_user.agent_id
    existing_agent_email = (
        db.query(Agent)
        .filter(Agent.email == agent_data.email)
        .first()
    )

    if existing_agent_email:
        raise HTTPException(
            status_code=400,
            detail="Member email already exists",
        )

    existing_user_email = (
        db.query(User)
        .filter(User.email == agent_data.email)
        .first()
    )

    if existing_user_email:
        raise HTTPException(
            status_code=400,
            detail="Login user already exists with this email",
        )

    if agent_data.parent_agent_id:
        parent = (
            db.query(Agent)
            .filter(Agent.id == agent_data.parent_agent_id)
            .first()
        )

        if not parent:
            raise HTTPException(
                status_code=404,
                detail="Parent member not found",
            )

    agent_code = generate_agent_code(db)

    agent_payload = agent_data.model_dump()
    agent_payload.pop("code", None)

    temp_password = generate_temp_password()

    try:
        agent = Agent(
            code=agent_code,
            **agent_payload,
        )

        db.add(agent)
        db.flush()
        db.refresh(agent)

        create_login_user_for_agent(
            db=db,
            agent=agent,
            temp_password=temp_password,
        )

        db.commit()
        db.refresh(agent)

        return {
            **AgentResponse.model_validate(agent).model_dump(),
            "temp_password": temp_password,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Member creation failed: {str(e)}",
        )


# ============================================================
# HIERARCHY TREE
# ============================================================

@router.get(
    "/hierarchy/tree",
    dependencies=[
        Depends(require_roles(["super_admin", "admin"]))
    ],
)
def get_agent_hierarchy(
    db: Session = Depends(get_db),
):
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

# ============================================================
# GET MY AGENT / MEMBER PROFILE
# ============================================================
# URL:
# GET /api/agents/me
#
# Purpose:
# Agent/member can view only own profile.

@router.get(
    "/me",
    response_model=AgentResponse,
)
def get_my_agent_profile(
    current_user: User = Depends(require_roles(["agent"])),
    db: Session = Depends(get_db),
):
    if not current_user.agent_id:
        raise HTTPException(
            status_code=404,
            detail="Agent profile not found",
        )

    agent = (
        db.query(Agent)
        .filter(Agent.id == current_user.agent_id)
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Agent profile not found",
        )

    return agent


@router.get(
    "/subagents",
    response_model=list[AgentResponse],
)
def get_my_subagents(
    current_user: User = Depends(require_roles(["agent"])),
    db: Session = Depends(get_db),
):
    if not current_user.agent_id:
        return []
    return (
        db.query(Agent)
        .filter(Agent.parent_agent_id == current_user.agent_id)
        .order_by(Agent.id.asc())
        .all()
    )


# ============================================================
# GET SINGLE AGENT / MEMBER
# ============================================================

@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    dependencies=[
        Depends(require_roles(["super_admin", "admin"]))
    ],
)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
):
    agent = (
        db.query(Agent)
        .filter(Agent.id == agent_id)
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Member not found",
        )

    return agent


# ============================================================
# UPDATE AGENT / MEMBER
# ============================================================

@router.put(
    "/{agent_id}",
    response_model=AgentResponse,
    dependencies=[
        Depends(require_roles(["super_admin", "admin"]))
    ],
)
def update_agent(
    agent_id: int,
    agent_data: AgentUpdate,
    db: Session = Depends(get_db),
):
    agent = (
        db.query(Agent)
        .filter(Agent.id == agent_id)
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Member not found",
        )

    existing_agent_email = (
        db.query(Agent)
        .filter(
            Agent.email == agent_data.email,
            Agent.id != agent_id,
        )
        .first()
    )

    if existing_agent_email:
        raise HTTPException(
            status_code=400,
            detail="Another member already uses this email",
        )

    linked_user = (
        db.query(User)
        .filter(User.agent_id == agent_id)
        .first()
    )

    existing_user_email = (
        db.query(User)
        .filter(User.email == agent_data.email)
        .first()
    )

    if existing_user_email and (
        not linked_user or existing_user_email.id != linked_user.id
    ):
        raise HTTPException(
            status_code=400,
            detail="Another login user already uses this email",
        )

    if agent_data.parent_agent_id:
        if agent_data.parent_agent_id == agent_id:
            raise HTTPException(
                status_code=400,
                detail="Member cannot be parent of itself",
            )

        parent = (
            db.query(Agent)
            .filter(Agent.id == agent_data.parent_agent_id)
            .first()
        )

        if not parent:
            raise HTTPException(
                status_code=404,
                detail="Parent member not found",
            )

        if is_circular_parent(
            db=db,
            agent_id=agent_id,
            new_parent_id=agent_data.parent_agent_id,
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid hierarchy. This parent selection creates circular network.",
            )

    agent.name = agent_data.name
    agent.email = agent_data.email
    agent.phone = agent_data.phone
    agent.address = agent_data.address
    agent.parent_agent_id = agent_data.parent_agent_id
    agent.status = agent_data.status
    agent.joined_date = agent_data.joined_date

    if linked_user:
        linked_user.name = agent_data.name
        linked_user.email = agent_data.email
        linked_user.status = agent_data.status

    db.commit()
    db.refresh(agent)

    return agent


# ============================================================
# DELETE AGENT / MEMBER
# ============================================================

@router.delete(
    "/{agent_id}",
    dependencies=[
        Depends(require_roles(["super_admin"]))
    ],
)
def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
):
    agent = (
        db.query(Agent)
        .filter(Agent.id == agent_id)
        .first()
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Member not found",
        )

    child_count = (
        db.query(Agent)
        .filter(Agent.parent_agent_id == agent_id)
        .count()
    )

    if child_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete this member because connected child members exist. First change or delete child members.",
        )

    # Check for orders referencing this agent
    order_count = (
        db.query(Order)
        .filter(Order.direct_agent_id == agent_id)
        .count()
    )

    if order_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete this member because {order_count} job(s) are assigned to them.",
        )

    # Check for commission payments referencing this agent
    payment_count = (
        db.query(CommissionPayment)
        .filter(CommissionPayment.agent_id == agent_id)
        .count()
    )

    if payment_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete this member because {payment_count} commission payment(s) reference them.",
        )

    linked_user = (
        db.query(User)
        .filter(User.agent_id == agent_id)
        .first()
    )

    if linked_user:
        db.delete(linked_user)

    db.delete(agent)
    db.commit()

    return {
        "message": "Member and linked login user deleted successfully",
        "deleted_member_id": agent_id,
    }