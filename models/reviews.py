"""Reviews, premium plans, and auditable platform revenue."""

from datetime import datetime

from extensions import db


class Review(db.Model):
    __tablename__ = "reviews"
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_id = db.Column(db.Integer, db.ForeignKey("learning_relationships.id", ondelete="CASCADE"), nullable=False, unique=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Published", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    learner = db.relationship("User", foreign_keys=[learner_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])
    relationship = db.relationship("LearningRelationship", backref=db.backref("review", uselist=False, cascade="all, delete-orphan"))
    skill = db.relationship("Skill")


class RevenueRecord(db.Model):
    __tablename__ = "revenue_records"
    id = db.Column(db.Integer, primary_key=True)
    source_type = db.Column(db.String(40), nullable=False, index=True)
    transaction_key = db.Column(db.String(120), nullable=False, unique=True)
    gross_amount = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    platform_commission = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    seller_earning = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    net_platform_revenue = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="Successful", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PremiumPlan(db.Model):
    __tablename__ = "premium_plans"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    price = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    duration_days = db.Column(db.Integer, nullable=False, default=30)
    description = db.Column(db.Text, nullable=True)
    features = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
