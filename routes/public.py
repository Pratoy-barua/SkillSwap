"""Public-facing pages and lightweight operational health endpoint."""

from flask import Blueprint, current_app, render_template
from sqlalchemy import text

from extensions import db
from models.auth import Location, MentorProfile, MentorSkill, Role, Skill, User


public_bp = Blueprint("public", __name__)


@public_bp.get("/")
def home():
    try:
        all_skills = Skill.query.filter_by(is_active=True).order_by(Skill.name.asc()).all()
        skills = all_skills[:8]
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
        all_skills, skills, featured, locations = [], [], [], []
    return render_template("public/home.html", page_title="Learn locally. Grow together.", skills=skills, all_skills=all_skills, featured=featured, locations=locations)


@public_bp.get("/about")
def about():
    return render_template("public/about.html", page_title="About Us")


@public_bp.get("/contact")
def contact():
    return render_template(
        "public/info_page.html",
        eyebrow="Contact",
        title="Get in touch with SkillSwap.",
        intro="For account, learning, or platform support, contact us through any of the details below.",
        sections=[
            ("Phone", "01741215105"),
            ("Email", "skillswap@gmail.com"),
            ("Address", "Syednagar B-Block, Notunbazar, Dhaka"),
            ("Open time", "11:00 AM – 10:00 PM"),
        ],
    )


@public_bp.get("/privacy")
def privacy():
    return render_template(
        "public/info_page.html",
        eyebrow="Privacy policy",
        title="Your information, handled carefully.",
        intro="This policy explains the information SkillSwap uses to operate the learning community and protect its members.",
        sections=[
            ("Information we collect", "We collect the details you provide when creating an account, including profile details, skills, location, learning activity, messages, purchases, and verification documents when submitted."),
            ("How information is used", "Information is used to create your account, connect learners and mentors, review applications, process demo payments and orders, provide support, and keep the platform safe."),
            ("Who can see your information", "Public profile information may be visible to people using SkillSwap. Verification documents remain protected and are available only to authorized administrators for review."),
            ("Security and retention", "Passwords are stored as secure hashes. We apply access controls to private uploads and retain information only for as long as needed to run the service, meet legal obligations, or resolve disputes."),
            ("Your choices", "You may update your profile information from your account. Contact the SkillSwap support team if you need help with an account, data, or privacy request."),
        ],
    )


@public_bp.get("/terms")
def terms():
    return render_template(
        "public/info_page.html",
        eyebrow="Terms & conditions",
        title="Using SkillSwap responsibly.",
        intro="By creating an account or using SkillSwap, you agree to follow these community rules.",
        sections=[
            ("Accurate accounts", "Provide accurate registration information and keep your password confidential. Do not create accounts for someone else or use another member's account."),
            ("Respectful community", "Treat learners, mentors, and administrators with respect. Harassment, fraud, discrimination, spam, and misleading profiles are not allowed."),
            ("Mentoring and learning", "Mentors are responsible for describing their experience honestly. Learners and mentors should agree on goals, schedules, fees, and expectations before starting an activity."),
            ("Payments and marketplace", "Payment and store features are provided for recorded platform transactions. Review prices, order details, and subscription terms before confirming a transaction."),
            ("Account actions", "SkillSwap may review, suspend, or remove accounts that violate these terms, create safety risks, or provide false information."),
        ],
    )


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
