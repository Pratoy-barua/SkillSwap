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


def get_mentor_unlock_fee(db_session=None):
    setting = PlatformSetting.query.filter_by(key="mentor_profile_unlock_fee").first()
    if not setting:
        if db_session:
            setting = PlatformSetting(key="mentor_profile_unlock_fee", value="50.00")
            db_session.add(setting)
            db_session.flush()
        else:
            return Decimal("50.00")
    try:
        return Decimal(setting.value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("50.00")


def generate_invoice_number(db_session=None):
    from extensions import db
    from models.learning import Payment
    session = db_session or db.session
    last_item = session.query(Payment).filter(Payment.invoice_number.isnot(None)).order_by(Payment.id.desc()).first()
    next_num = (last_item.id + 1) if last_item else (session.query(Payment).count() + 1)
    while True:
        candidate = f"INV-{next_num:04d}"
        if not session.query(Payment).filter_by(invoice_number=candidate).first():
            return candidate
        next_num += 1


def check_and_update_overdue_payments():
    from datetime import date
    from extensions import db
    from models.connection import Notification
    from models.learning import Payment
    from services.notifications import notify

    overdue_items = Payment.query.filter(
        Payment.status.in_(["Pending", "pending"]),
        Payment.due_date.isnot(None),
        Payment.due_date < date.today(),
    ).all()

    for item in overdue_items:
        item.status = "Overdue"
        existing_learner_notif = Notification.query.filter_by(
            user_id=item.learner_id,
            notification_type="payment_overdue",
            related_type="payment",
            related_id=item.id,
        ).first()
        if not existing_learner_notif:
            notify(
                item.learner_id,
                "payment_overdue",
                "Payment Overdue",
                f"Your payment for invoice {item.display_invoice_number} is overdue.",
                "payment",
                item.id,
            )
            notify(
                item.mentor_id,
                "payment_overdue",
                "Payment Overdue",
                f"Invoice {item.display_invoice_number} for {item.learner.full_name} is overdue.",
                "payment",
                item.id,
            )
    if overdue_items:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


def create_invoice_request(relationship, amount, due_date, description=None, billing_period=None, payment_type=None, frequency=None):
    from datetime import datetime
    from extensions import db
    from models.learning import Payment
    from services.notifications import notify

    amount = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    p_type = payment_type or relationship.payment_type or "one_time"
    p_freq = frequency or relationship.payment_frequency or ("none" if p_type == "one_time" else "weekly")
    inv_num = generate_invoice_number(db.session)
    ref_id = f"REF-{uuid4().hex[:12].upper()}"

    desc = (description or "").strip()
    if not desc:
        if p_type == "recurring":
            desc = f"{relationship.skill.name} Mentorship - {p_freq.capitalize()} ({billing_period or 'Payment'})"
        else:
            desc = f"{relationship.skill.name} Mentorship - One-time Payment"

    amount, commission, mentor_earning = split_amount(amount, db.session)

    payment = Payment(
        learner_id=relationship.learner_id,
        mentor_id=relationship.mentor_id,
        relationship_id=relationship.id,
        skill_id=relationship.skill_id,
        invoice_number=inv_num,
        amount=amount,
        payment_type=p_type,
        frequency=p_freq,
        description=desc,
        billing_period=billing_period or ("One-time" if p_type == "one_time" else f"{p_freq.capitalize()} billing"),
        due_date=due_date,
        reference_id=ref_id,
        status="Pending",
        platform_commission=commission,
        mentor_earning=mentor_earning,
        created_at=datetime.utcnow(),
    )
    db.session.add(payment)
    db.session.commit()

    due_str = due_date.strftime("%d %b %Y") if hasattr(due_date, "strftime") and due_date else "Immediate"
    amount_str = f"{int(amount)}" if amount == int(amount) else f"{amount:.2f}"
    notify(
        relationship.learner_id,
        "payment_invoice_created",
        "New Payment Request",
        f"New payment request from {relationship.mentor.full_name}: ৳{amount_str} due on {due_str}.",
        "payment",
        payment.id,
    )
    return payment


def process_invoice_payment(payment, payer_user):
    from datetime import datetime
    from extensions import db
    from models.learning import PaymentTransaction
    from services.notifications import notify
    from services.revenue import record_revenue

    if payment.status in ("Paid", "Successful") or payment.paid_at is not None:
        raise ValueError("This invoice has already been paid.")

    amount, commission, mentor_earning = split_amount(payment.amount, db.session)
    demo_ref = f"DEMO-{uuid4().hex.upper()}"

    payment.status = "Paid"
    payment.paid_at = datetime.utcnow()
    payment.payment_date = datetime.utcnow()
    payment.reference_id = demo_ref
    payment.platform_commission = commission
    payment.mentor_earning = mentor_earning

    txn = PaymentTransaction(
        payment_id=payment.id,
        payer_id=payer_user.id,
        amount=payment.amount,
        platform_fee=commission,
        mentor_amount=mentor_earning,
        status="Successful",
        transaction_reference=demo_ref,
        created_at=datetime.utcnow(),
        paid_at=datetime.utcnow(),
    )
    db.session.add(txn)

    record_revenue("Mentor Payment", payment.id, payment.amount, commission, mentor_earning)

    notify(
        payment.mentor_id,
        "payment_received",
        "Payment Received",
        f"{payer_user.full_name} paid invoice {payment.display_invoice_number}.",
        "payment",
        payment.id,
    )
    notify(
        payment.learner_id,
        "payment_successful",
        "Payment Successful",
        f"Payment successful. Invoice {payment.display_invoice_number} has been marked as paid.",
        "payment",
        payment.id,
    )
    db.session.commit()
    return payment


def get_mentor_balance_summary(mentor_id, session=None):
    from decimal import Decimal
    from extensions import db
    from models.learning import Payment, Withdrawal

    s = session or db.session
    payments = s.query(Payment).filter_by(mentor_id=mentor_id).all()
    paid_payments = [p for p in payments if p.display_status == "Paid"]
    total_earnings = sum((Decimal(str(p.mentor_earning or 0)) for p in paid_payments), Decimal("0.00"))

    withdrawals = s.query(Withdrawal).filter_by(mentor_id=mentor_id).order_by(Withdrawal.requested_at.desc()).all()
    total_withdrawn = sum((Decimal(str(w.amount or 0)) for w in withdrawals if w.status == "Completed"), Decimal("0.00"))
    pending_withdrawals = sum((Decimal(str(w.amount or 0)) for w in withdrawals if w.status in ("Pending", "Processing")), Decimal("0.00"))

    available_balance = total_earnings - total_withdrawn - pending_withdrawals
    if available_balance < Decimal("0.00"):
        available_balance = Decimal("0.00")

    return {
        "total_earnings": total_earnings,
        "total_withdrawn": total_withdrawn,
        "pending_withdrawals": pending_withdrawals,
        "available_balance": available_balance,
        "withdrawals": withdrawals,
    }


def generate_withdrawal_id(session=None):
    from extensions import db
    from models.learning import Withdrawal

    s = session or db.session
    last = s.query(Withdrawal).order_by(Withdrawal.id.desc()).first()
    next_num = (last.id + 1) if last else 1
    candidate = f"WD-{next_num:04d}"
    while s.query(Withdrawal).filter_by(withdrawal_id=candidate).first():
        next_num += 1
        candidate = f"WD-{next_num:04d}"
    return candidate


def create_withdrawal_request(mentor_id, amount_val, method, form_data, session=None):
    import re
    from datetime import datetime, timedelta
    from decimal import Decimal, InvalidOperation
    from extensions import db
    from models.auth import Role, User
    from models.learning import Withdrawal
    from services.notifications import notify

    s = session or db.session

    try:
        amount = Decimal(str(amount_val).strip()).quantize(Decimal("0.01"))
        if amount <= Decimal("0.00"):
            raise ValueError("Withdrawal amount must be greater than zero.")
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Please enter a valid withdrawal amount.")

    balance_info = get_mentor_balance_summary(mentor_id, session=s)
    available = balance_info["available_balance"]

    if amount > available:
        raise ValueError("Insufficient available balance.")

    allowed_methods = {"bKash", "Nagad", "Rocket", "Bank Account", "Card"}
    if method not in allowed_methods:
        raise ValueError("Please select a valid withdrawal method.")

    # Duplicate submission guard: check if identical request was submitted in last 5 seconds
    recent_dup = s.query(Withdrawal).filter(
        Withdrawal.mentor_id == mentor_id,
        Withdrawal.amount == amount,
        Withdrawal.method == method,
        Withdrawal.status == "Pending",
        Withdrawal.requested_at >= datetime.utcnow() - timedelta(seconds=5),
    ).first()
    if recent_dup:
        raise ValueError("Your withdrawal request is already being processed.")

    holder_name = (form_data.get("account_holder_name") or "").strip()
    account_number = ""
    bank_name = None
    branch_name = None
    routing_number = None
    card_issuer = None
    card_last4 = None

    if method in ("bKash", "Nagad"):
        raw_number = (form_data.get("account_number") or form_data.get("bkash_number") or form_data.get("nagad_number") or "").strip().replace(" ", "").replace("-", "")
        if not re.match(r"^01[3-9]\d{8}$", raw_number):
            raise ValueError(f"Please enter a valid 11-digit Bangladeshi mobile number for {method} (e.g. 017XXXXXXXX).")
        if not holder_name:
            raise ValueError("Please provide the account holder name.")
        account_number = raw_number

    elif method == "Rocket":
        raw_number = (form_data.get("account_number") or form_data.get("rocket_number") or "").strip().replace(" ", "").replace("-", "")
        if not re.match(r"^01[3-9]\d{8,9}$", raw_number):
            raise ValueError("Please enter a valid 11 or 12-digit Rocket mobile account number.")
        if not holder_name:
            raise ValueError("Please provide the account holder name.")
        account_number = raw_number

    elif method == "Bank Account":
        bank_name = (form_data.get("bank_name") or "").strip()
        raw_acc = (form_data.get("account_number") or form_data.get("bank_account_number") or "").strip().replace(" ", "").replace("-", "")
        branch_name = (form_data.get("branch_name") or "").strip()
        routing_number = (form_data.get("routing_number") or "").strip()

        if not bank_name:
            raise ValueError("Please provide the Bank Name.")
        if not holder_name:
            raise ValueError("Please provide the Account Holder Name.")
        if not raw_acc or len(raw_acc) < 6:
            raise ValueError("Please provide a valid Bank Account Number.")
        if not branch_name:
            raise ValueError("Please provide the Branch Name.")
        account_number = raw_acc

    elif method == "Card":
        raw_card = (form_data.get("card_number") or "").strip().replace(" ", "").replace("-", "")
        card_issuer = (form_data.get("card_issuer") or "").strip() or None
        if not holder_name:
            raise ValueError("Please provide the Card Holder Name.")
        if not raw_card.isdigit() or len(raw_card) < 13 or len(raw_card) > 19:
            raise ValueError("Please enter a valid card number (13-19 digits).")
        # NEVER store CVV or full raw card number!
        card_last4 = raw_card[-4:]
        account_number = f"**** **** **** {card_last4}"

    withdrawal_id = generate_withdrawal_id(session=s)

    withdrawal = Withdrawal(
        withdrawal_id=withdrawal_id,
        mentor_id=mentor_id,
        amount=amount,
        method=method,
        status="Pending",
        account_holder_name=holder_name,
        account_number=account_number,
        bank_name=bank_name,
        branch_name=branch_name,
        routing_number=routing_number,
        card_issuer=card_issuer,
        card_last4=card_last4,
        requested_at=datetime.utcnow(),
    )
    s.add(withdrawal)
    s.commit()

    # Notify mentor
    mentor = s.query(User).get(mentor_id)
    mentor_name = mentor.full_name if mentor else "Mentor"
    notify(
        mentor_id,
        "withdrawal_requested",
        "Withdrawal Requested",
        f"Your withdrawal request {withdrawal_id} for ৳{amount:.2f} via {method} was submitted successfully.",
        "withdrawal",
        withdrawal.id,
    )

    # Notify admins
    admins = User.query.join(User.role).filter(Role.name == "Admin").all()
    for admin in admins:
        notify(
            admin.id,
            "admin_withdrawal_requested",
            "New Withdrawal Request",
            f"Mentor {mentor_name} requested withdrawal {withdrawal_id} for ৳{amount:.2f} via {method}.",
            "withdrawal",
            withdrawal.id,
        )

    return withdrawal



