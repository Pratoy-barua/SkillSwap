"""Persisted notification creation shared by connection workflows."""

from extensions import db
from models.connection import Notification


def notify(user_id, notification_type, title, message, related_type=None, related_id=None):
    item = Notification(
        user_id=user_id,
        notification_type=notification_type,
        title=title,
        message=message,
        related_type=related_type,
        related_id=related_id,
    )
    db.session.add(item)
    return item
