"""Idempotent revenue ledger helpers."""

from decimal import Decimal

from extensions import db
from models.reviews import RevenueRecord


def record_revenue(source_type, transaction_key, gross_amount, platform_commission=0, seller_earning=0, status="Successful"):
    key = f"{source_type}:{transaction_key}"
    record = RevenueRecord.query.filter_by(transaction_key=key).first()
    gross = Decimal(str(gross_amount or 0))
    commission = Decimal(str(platform_commission or 0))
    earning = Decimal(str(seller_earning or 0))
    if not record:
        record = RevenueRecord(source_type=source_type, transaction_key=key)
        db.session.add(record)
    record.gross_amount = gross
    record.platform_commission = commission
    record.seller_earning = earning
    record.net_platform_revenue = gross - earning
    record.status = status
    return record
