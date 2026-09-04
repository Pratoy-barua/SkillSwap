"""Premium access checks kept separate from route handlers."""

from datetime import date

from extensions import db
from models.learning import Subscription


def active_subscription(user_id):
    item = Subscription.query.filter_by(user_id=user_id, status="Active").order_by(Subscription.expiry_date.desc()).first()
    if item and item.expiry_date and item.expiry_date < date.today():
        item.status = "Expired"
        db.session.commit()
        return None
    return item


def has_premium(user_id):
    return active_subscription(user_id) is not None
