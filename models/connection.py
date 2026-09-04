"""Learner-mentor requests, relationships, chat, and notifications."""

from datetime import datetime

from extensions import db


class LearningRequest(db.Model):
    __tablename__ = "learning_requests"
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    learner = db.relationship("User", foreign_keys=[learner_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])
    skill = db.relationship("Skill")
    relationship = db.relationship("LearningRelationship", back_populates="request", uselist=False)
    __table_args__ = (db.Index("ix_learning_request_pair_status", "learner_id", "mentor_id", "skill_id", "status"),)


class LearningRelationship(db.Model):
    __tablename__ = "learning_relationships"
    id = db.Column(db.Integer, primary_key=True)
    learner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    mentor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey("learning_requests.id", ondelete="SET NULL"), unique=True, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Active", index=True)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    learner = db.relationship("User", foreign_keys=[learner_id])
    mentor = db.relationship("User", foreign_keys=[mentor_id])
    skill = db.relationship("Skill")
    request = db.relationship("LearningRequest", back_populates="relationship")
    conversation = db.relationship("Conversation", back_populates="relationship", uselist=False, cascade="all, delete-orphan")
    plan = db.relationship("LearningPlan", back_populates="relationship", uselist=False, cascade="all, delete-orphan")
    progress = db.relationship("LearningProgress", back_populates="relationship", uselist=False, cascade="all, delete-orphan")
    __table_args__ = (db.UniqueConstraint("learner_id", "mentor_id", "skill_id", "status", name="uq_active_learning_relationship"),)


class Conversation(db.Model):
    __tablename__ = "conversations"
    id = db.Column(db.Integer, primary_key=True)
    relationship_id = db.Column(db.Integer, db.ForeignKey("learning_relationships.id", ondelete="CASCADE"), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    relationship = db.relationship("LearningRelationship", back_populates="conversation")
    messages = db.relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    conversation = db.relationship("Conversation", back_populates="messages")
    sender = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_type = db.Column(db.String(40), nullable=True)
    related_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    user = db.relationship("User")
