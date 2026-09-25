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
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_type = db.Column(db.String(30), nullable=False)
    reference_id = db.Column(db.String(80), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    platform_commission = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    mentor_earning = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    learner = db.relationship("User", foreign_keys=[learner_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])
    relationship = db.relationship("LearningRelationship")


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

