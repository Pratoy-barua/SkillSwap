"""Authentication, profile, skill, location, and verification models."""

from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


class Role(db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), unique=True, nullable=False)
    users = db.relationship("User", back_populates="role")


class Location(db.Model):
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(120), nullable=True)
    country = db.Column(db.String(120), nullable=False, default="Bangladesh")
    latitude = db.Column(db.Numeric(10, 7), nullable=True)
    longitude = db.Column(db.Numeric(10, 7), nullable=True)
    __table_args__ = (db.UniqueConstraint("city", "area", "country", name="uq_location"),)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    full_name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(40), nullable=False)
    address = db.Column(db.String(255), nullable=False, default="")
    password_hash = db.Column(db.String(255), nullable=False)
    profile_photo = db.Column(db.String(255), nullable=True)
    account_status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    role = db.relationship("Role", back_populates="users")
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    location = db.relationship("Location")
    learner_profile = db.relationship("LearnerProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    mentor_profile = db.relationship("MentorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    documents = db.relationship("VerificationDocument", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return self.account_status not in {"Suspended", "Rejected"}

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class LearnerProfile(db.Model):
    __tablename__ = "learner_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    bio = db.Column(db.Text, nullable=True)
    interests = db.Column(db.Text, nullable=True)
    user = db.relationship("User", back_populates="learner_profile")
    skills = db.relationship("LearnerSkill", cascade="all, delete-orphan", back_populates="learner_profile")


class MentorProfile(db.Model):
    __tablename__ = "mentor_profiles"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    bio = db.Column(db.Text, nullable=False)
    experience = db.Column(db.String(120), nullable=False)
    teaching_type = db.Column(db.String(120), nullable=False)
    is_paid = db.Column(db.Boolean, nullable=False, default=False)
    pricing = db.Column(db.Numeric(10, 2), nullable=True)
    rating = db.Column(db.Numeric(3, 2), nullable=False, default=0)
    user = db.relationship("User", back_populates="mentor_profile")
    skills = db.relationship("MentorSkill", cascade="all, delete-orphan", back_populates="mentor_profile")


class Skill(db.Model):
    __tablename__ = "skills"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    icon = db.Column(db.String(255), nullable=True)


class LearnerSkill(db.Model):
    __tablename__ = "learner_skills"
    learner_id = db.Column(db.Integer, db.ForeignKey("learner_profiles.id", ondelete="CASCADE"), primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    learner_profile = db.relationship("LearnerProfile", back_populates="skills")
    skill = db.relationship("Skill")


class MentorSkill(db.Model):
    __tablename__ = "mentor_skills"
    mentor_profile_id = db.Column(db.Integer, db.ForeignKey("mentor_profiles.id", ondelete="CASCADE"), primary_key=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.id", ondelete="CASCADE"), primary_key=True)
    experience = db.Column(db.String(120), nullable=True)
    is_paid = db.Column(db.Boolean, nullable=False, default=False)
    price = db.Column(db.Numeric(10, 2), nullable=True)
    pricing_type = db.Column(db.String(30), nullable=False, default="Course-based")
    mentor_profile = db.relationship("MentorProfile", back_populates="skills")
    skill = db.relationship("Skill")


class VerificationDocument(db.Model):
    __tablename__ = "verification_documents"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = db.Column(db.String(40), nullable=False)
    original_name = db.Column(db.String(255), nullable=False)
    stored_name = db.Column(db.String(255), unique=True, nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship("User", back_populates="documents")
