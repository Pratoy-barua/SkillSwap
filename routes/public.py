"""Public-facing pages and lightweight operational health endpoint."""

from flask import Blueprint, current_app, render_template
from sqlalchemy import text

from extensions import db
from models.auth import Location, MentorProfile, MentorSkill, Role, Skill, User


public_bp = Blueprint("public", __name__)


@public_bp.get("/")
def home():
    try:
        skills = Skill.query.filter_by(is_active=True).order_by(Skill.name.asc()).limit(8).all()
        featured = (
            MentorSkill.query.join(MentorSkill.mentor_profile)
            .join(MentorProfile.user)
            .join(User.role)
            .join(MentorSkill.skill)
            .filter(User.account_status == "Approved", Role.name == "Mentor", Skill.is_active.is_(True))
            .order_by(User.created_at.desc())
            .limit(6).all()
        )
        locations = Location.query.join(User, User.location_id == Location.id).join(User.role).filter(Role.name == "Mentor", User.account_status == "Approved").distinct().order_by(Location.city, Location.area).all()
    except Exception:
        # Keep the Phase 1 marketing page available while the database is starting.
        skills, featured, locations = [], [], []
    return render_template("public/home.html", page_title="Learn locally. Grow together.", skills=skills, featured=featured, locations=locations)


@public_bp.get("/about")
def about():
    return render_template("public/placeholder.html", feature="About SkillSwap")


@public_bp.get("/contact")
def contact():
    return render_template("public/placeholder.html", feature="Contact SkillSwap")


@public_bp.get("/skills")
def skills():
    from routes.discovery import skills as skill_index

    return skill_index()


@public_bp.get("/store")
def store():
    from routes.store import index as store_index

    return store_index()


@public_bp.get("/become-a-mentor")
def become_a_mentor():
    return render_template("public/mentor_choice.html")


@public_bp.get("/login")
def login():
    return render_template("auth/login.html")


@public_bp.get("/sign-up")
def sign_up():
    return render_template("public/signup_choice.html")


@public_bp.get("/health")
def health():
    """Return readiness information without exposing connection details."""
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return {"status": "degraded", "database": "unavailable"}, 503

    return {
        "status": "ok",
        "database": "connected",
        "environment": "development" if current_app.debug else "production",
    }
