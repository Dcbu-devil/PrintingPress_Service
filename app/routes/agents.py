from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Agent
from app.schemas import AgentCreate, AgentUpdate, AgentResponse
from app.auth import require_roles


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
# Main responsibilities:
# 1. Get all members
# 2. Create member
# 3. Get member hierarchy/tree
# 4. Get single member
# 5. Update member
# 6. Delete member
#
# Permission rules:
# 1. super_admin and admin can view members.
# 2. super_admin and admin can create members.
# 3. super_admin and admin can update members.
# 4. only super_admin can delete members.
# 5. super_admin and admin can view hierarchy tree.

router = APIRouter(
    prefix="/api/agents",
    tags=["Agents"],
)


# ============================================================
# HELPER: GENERATE SEQUENTIAL MEMBER CODE
# ============================================================
# Purpose:
# Generates member codes like:
#
# AG001
# AG002
# AG003
#
# Current MVP:
# Uses last database ID to generate next code.
#
# Later production improvement:
# Use database sequence or UUID to avoid duplicate issues
# when many users create members at the same time.

def generate_agent_code(
    db: Session,
):
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


# ============================================================
# HELPER: CHECK CIRCULAR HIERARCHY
# ============================================================
# Purpose:
# Prevents invalid member hierarchy.
#
# Example invalid case:
# Ravi is parent of Sibu.
# Then Ravi cannot set Sibu as his own parent.
#
# Why needed:
# Without this check, network tree can become broken/infinite loop.

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
# GET ALL AGENTS / MEMBERS
# ============================================================
# URL:
# GET /api/agents/
#
# Permission:
# super_admin, admin
#
# Purpose:
# Returns all members in ascending order.
#
# Used by:
# Members page
# Add Job page
# Dashboard page

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
# Permission:
# super_admin, admin
#
# Purpose:
# Creates a new member.
#
# Important:
# Member code is generated automatically by backend.
# Frontend does not need to send code.

@router.post(
    "/",
    response_model=AgentResponse,
    dependencies=[
        Depends(require_roles(["super_admin", "admin"]))
    ],
)
def create_agent(
    agent_data: AgentCreate,
    db: Session = Depends(get_db),
):
    # ========================================================
    # CHECK DUPLICATE EMAIL
    # ========================================================

    existing_email = (
        db.query(Agent)
        .filter(Agent.email == agent_data.email)
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Member email already exists",
        )

    # ========================================================
    # VALIDATE PARENT MEMBER
    # ========================================================
    # If parent_agent_id is provided, that parent must exist.

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

    # ========================================================
    # GENERATE MEMBER CODE
    # ========================================================

    agent_code = generate_agent_code(db)

    # Remove code from frontend payload if accidentally sent.
    # Backend should control member code generation.

    agent_payload = agent_data.model_dump()
    agent_payload.pop("code", None)

    # ========================================================
    # CREATE MEMBER OBJECT
    # ========================================================

    agent = Agent(
        code=agent_code,
        **agent_payload,
    )

    db.add(agent)
    db.commit()
    db.refresh(agent)

    return agent


# ============================================================
# HIERARCHY TREE
# ============================================================
# URL:
# GET /api/agents/hierarchy/tree
#
# Permission:
# super_admin, admin
#
# Purpose:
# Returns members in parent-child tree format.
#
# Important:
# Keep this route BEFORE /{agent_id}
# Otherwise FastAPI may treat "hierarchy/tree" as agent_id.

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

    # ========================================================
    # CREATE AGENT MAP
    # ========================================================
    # Convert each agent row into dictionary with children list.

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

    # ========================================================
    # BUILD TREE STRUCTURE
    # ========================================================
    # If an agent has parent, add it inside parent's children.
    # Otherwise, add it as root member.

    for agent in agents:
        current_agent = agent_map[agent.id]

        if agent.parent_agent_id and agent.parent_agent_id in agent_map:
            agent_map[agent.parent_agent_id]["children"].append(current_agent)
        else:
            root_agents.append(current_agent)

    return root_agents


# ============================================================
# GET SINGLE AGENT / MEMBER
# ============================================================
# URL:
# GET /api/agents/{agent_id}
#
# Permission:
# super_admin, admin
#
# Purpose:
# Returns one member by database ID.

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
# URL:
# PUT /api/agents/{agent_id}
#
# Permission:
# super_admin, admin
#
# Purpose:
# Updates member details.
#
# Safety validations:
# 1. Member must exist.
# 2. Email cannot be used by another member.
# 3. Member cannot be parent of itself.
# 4. Parent member must exist.
# 5. Circular hierarchy is blocked.

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
    # ========================================================
    # FIND MEMBER
    # ========================================================

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

    # ========================================================
    # CHECK DUPLICATE EMAIL
    # ========================================================

    existing_email = (
        db.query(Agent)
        .filter(
            Agent.email == agent_data.email,
            Agent.id != agent_id,
        )
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=400,
            detail="Another member already uses this email",
        )

    # ========================================================
    # VALIDATE PARENT MEMBER
    # ========================================================

    if agent_data.parent_agent_id:
        # Member cannot become parent of itself.
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

        # Prevent circular hierarchy.
        if is_circular_parent(
            db=db,
            agent_id=agent_id,
            new_parent_id=agent_data.parent_agent_id,
        ):
            raise HTTPException(
                status_code=400,
                detail="Invalid hierarchy. This parent selection creates circular network.",
            )

    # ========================================================
    # UPDATE MEMBER FIELDS
    # ========================================================

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


# ============================================================
# DELETE AGENT / MEMBER
# ============================================================
# URL:
# DELETE /api/agents/{agent_id}
#
# Permission:
# super_admin only
#
# Purpose:
# Deletes a member.
#
# Safety rule:
# A member cannot be deleted if child members are connected.
#
# Example:
# If Ravi has Sibu as child member,
# Ravi cannot be deleted until Sibu is moved/deleted.

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

    # ========================================================
    # CHECK CHILD MEMBERS
    # ========================================================
    # Do not allow delete if this member has child members.

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

    db.delete(agent)
    db.commit()

    return {
        "message": "Member deleted successfully",
        "deleted_member_id": agent_id,
    }