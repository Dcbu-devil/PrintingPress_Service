from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Notification, User
from app.schemas import NotificationResponse
from app.auth import get_current_user, require_roles

router = APIRouter(
    prefix="/api/notifications",
    tags=["Notifications"],
)

# ============================================================
# GET UNREAD NOTIFICATIONS
# ============================================================
# URL:
# GET /api/notifications/
#
# Permission:
# super_admin, admin

@router.get(
    "/",
    response_model=list[NotificationResponse],
    dependencies=[Depends(require_roles(["super_admin", "admin"]))],
)
def get_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Fetch all unread notifications for super admin or admin
    # (where user_id is None or user_id == current_user.id)
    return (
        db.query(Notification)
        .filter(
            Notification.is_read == False,
            (Notification.user_id == None) | (Notification.user_id == current_user.id)
        )
        .order_by(Notification.id.desc())
        .all()
    )


# ============================================================
# MARK NOTIFICATION AS READ
# ============================================================
# URL:
# PUT /api/notifications/{notification_id}/read
#
# Permission:
# super_admin, admin

@router.put(
    "/{notification_id}/read",
    dependencies=[Depends(require_roles(["super_admin", "admin"]))],
)
def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
):
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id)
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    notification.is_read = True
    db.commit()

    return {"message": "Notification marked as read"}
