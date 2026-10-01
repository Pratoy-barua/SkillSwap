"""Learning plans, progress, payments, subscriptions, and settings."""

from datetime import datetime

from extensions import db


class LearningPlan(db.Model):
    __tablename__ = "learning_plans"
    id = db.Column(db.Integer, primary_key=True)
    relationship_id = db.Column(db.Integer, db.ForeignKey("learning_relationships.id", ondelete="CASCADE"), unique=True, nullable=False)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    pricing = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    pricing_type = db.Column(db.String(30), nullable=False, default="Course-based")
    start_date = db.Column(db.Date, nullable=False)
    expected_completion_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    relationship = db.relationship("LearningRelationship", back_populates="plan")


class LearningProgress(db.Model):
    __tablename__ = "learning_progress"
    id = db.Column(db.Integer, primary_key=True)
    relationship_id = db.Column(db.Integer, db.ForeignKey("learning_relationships.id", ondelete="CASCADE"), unique=True, nullable=False)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    percentage = db.Column(db.Integer, nullable=False, default=0)
    completed_topics = db.Column(db.Text, nullable=True)
    current_topic = db.Column(db.String(180), nullable=True)
    remaining_topics = db.Column(db.Text, nullable=True)
    mentor_notes = db.Column(db.Text, nullable=True)
    completion_status = db.Column(db.String(20), nullable=False, default="In Progress")
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    relationship = db.relationship("LearningRelationship", back_populates="progress")
    learner = db.relationship("User", foreign_keys=[learner_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])
    skill = db.relationship("Skill")


class Payment(db.Model):
    __tablename__ = "payments"
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_id = db.Column(db.Integer, db.ForeignKey("learning_relationships.id", ondelete="SET NULL"), nullable=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="SET NULL"), nullable=True)
    invoice_number = db.Column(db.String(40), unique=True, nullable=True, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_type = db.Column(db.String(30), nullable=False, default="one_time")
    frequency = db.Column(db.String(20), nullable=False, default="none")
    description = db.Column(db.String(255), nullable=True)
    billing_period = db.Column(db.String(100), nullable=True)
    due_date = db.Column(db.Date, nullable=True, index=True)
    reference_id = db.Column(db.String(80), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    platform_commission = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    mentor_earning = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    learner = db.relationship("User", foreign_keys=[learner_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])
    relationship = db.relationship("LearningRelationship", back_populates="payments")
    skill = db.relationship("Skill")

    @property
    def display_invoice_number(self):
        return self.invoice_number or f"INV-{self.id:04d}"

    @property
    def display_payment_type(self):
        if self.payment_type in ("one_time", "One-time", "One-Time"):
            return "One-time"
        if self.payment_type in ("recurring", "Recurring"):
            return "Recurring"
        return self.payment_type

    @property
    def display_frequency(self):
        if self.frequency in ("weekly", "Weekly"):
            return "Weekly"
        if self.frequency in ("monthly", "Monthly"):
            return "Monthly"
        if self.frequency in ("none", "None", ""):
            return "One-time" if self.display_payment_type == "One-time" else "None"
        return self.frequency.capitalize()

    @property
    def display_status(self):
        from datetime import date
        if self.status in ("Paid", "paid", "Successful"):
            return "Paid"
        if self.status in ("Cancelled", "cancelled"):
            return "Cancelled"
        if self.due_date and self.due_date < date.today() and self.status in ("Pending", "pending", "Overdue", "overdue"):
            return "Overdue"
        if self.status in ("Pending", "pending"):
            return "Pending"
        return self.status

    @property
    def effective_paid_date(self):
        return self.paid_at or self.payment_date


class PaymentTransaction(db.Model):
    __tablename__ = "payment_transactions"
    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    payer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    platform_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    mentor_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="Successful")
    transaction_reference = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)

    payment = db.relationship("Payment", backref=db.backref("transactions", cascade="all, delete-orphan"))
    payer = db.relationship("User", foreign_keys=[payer_id])


# Alias PaymentInvoice to Payment for convenient semantic usage
PaymentInvoice = Payment


class Subscription(db.Model):
    __tablename__ = "subscriptions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan = db.Column(db.String(40), nullable=False, default="Free")
    amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    start_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    payment_reference = db.Column(db.String(80), nullable=True)
    premium_plan_id = db.Column(db.Integer, db.ForeignKey("premium_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    user = db.relationship("User")
    premium_plan = db.relationship("PremiumPlan")


class PlatformSetting(db.Model):
    __tablename__ = "platform_settings"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class MentorProfileAccess(db.Model):
    __tablename__ = "mentor_profile_accesses"
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)
    unlocked_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("learner_id", "mentor_id", name="uq_learner_mentor_profile_access"),
    )

    learner = db.relationship("User", foreign_keys=[learner_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])
    payment = db.relationship("Payment")


class Withdrawal(db.Model):
    __tablename__ = "withdrawals"
    id = db.Column(db.Integer, primary_key=True)
    withdrawal_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    method = db.Column(db.String(40), nullable=False)  # bKash, Nagad, Rocket, Bank Account, Card
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)  # Pending, Processing, Completed, Rejected, Cancelled
    account_holder_name = db.Column(db.String(120), nullable=True)
    account_number = db.Column(db.String(80), nullable=True)
    bank_name = db.Column(db.String(120), nullable=True)
    branch_name = db.Column(db.String(120), nullable=True)
    routing_number = db.Column(db.String(50), nullable=True)
    card_issuer = db.Column(db.String(80), nullable=True)
    card_last4 = db.Column(db.String(4), nullable=True)
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    admin_note = db.Column(db.Text, nullable=True)

    mentor = db.relationship("User", foreign_keys=[mentor_id])

    @property
    def display_withdrawal_id(self):
        return self.withdrawal_id or f"WD-{self.id:04d}"

    @property
    def masked_account_display(self):
        if self.method in ("bKash", "Nagad", "Rocket"):
            acc = self.account_number or ""
            if len(acc) >= 8:
                return f"{acc[:2]}******{acc[-3:]}"
            return acc or "-"
        elif self.method == "Bank Account":
            acc = self.account_number or ""
            masked = f"******{acc[-4:]}" if len(acc) > 4 else acc
            details = [self.bank_name, self.branch_name, masked]
            return " · ".join([d for d in details if d])
        elif self.method == "Card":
            last4 = self.card_last4 or (self.account_number[-4:] if self.account_number else "****")
            issuer = f" ({self.card_issuer})" if self.card_issuer else ""
            return f"**** **** **** {last4}{issuer}"
        return self.account_number or "-"


