from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.auth_service import get_current_user, TokenData
from app.chat.database import get_db
from app.chat.models import Notification

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"]
)
@router.get("")
async def get_notifications(
    db: Session = Depends(get_db),
    user: TokenData = Depends(get_current_user)
):
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.user_id)
        .order_by(Notification.created_at.desc())
        .all()
    )

    return [
        {
            "id": n.id,
            "notification_type": n.notification_type,
            "message": n.message,
            "is_read": n.is_read,
            "ref_type": n.ref_type,
            "ref_id": n.ref_id,
            "created_at": n.created_at,
        }
        for n in notifications
    ]
@router.patch("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    user: TokenData = Depends(get_current_user)
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == user.user_id
        )
        .first()
    )

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found"
        )

    notification.is_read = True

    db.commit()
    db.refresh(notification)

    return {
        "message": "Notification marked as read",
        "notification_id": notification.id,
        "is_read": notification.is_read
    }
@router.patch("/read-all")
async def mark_all_notifications_read(
    db: Session = Depends(get_db),
    user: TokenData = Depends(get_current_user)
):
    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == user.user_id,
            Notification.is_read == False
        )
        .all()
    )

    count = len(notifications)

    for notification in notifications:
        notification.is_read = True

    db.commit()

    return {
        "message": f"{count} notifications marked as read"
    }