"""Payment provider abstraction with an explicitly non-financial demo provider."""

from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from models.learning import PlatformSetting


class DemoPaymentProvider:
    name = "demo"

    def charge(self, amount, outcome="success"):
        # This deliberately creates no external financial transaction.
        return {"status": "Successful" if outcome == "success" else "Failed", "reference_id": f"DEMO-{uuid4().hex.upper()}"}


def commission_rate(db_session):
    setting = PlatformSetting.query.filter_by(key="platform_commission_percent").first()
    if not setting:
        setting = PlatformSetting(key="platform_commission_percent", value="10")
        db_session.add(setting)
        db_session.flush()
    try:
        return Decimal(setting.value)
    except Exception:
        return Decimal("10")


def split_amount(amount, db_session):
    amount = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    commission = (amount * commission_rate(db_session) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return amount, commission, amount - commission
