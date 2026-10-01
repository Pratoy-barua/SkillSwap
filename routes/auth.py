"""Learner, mentor, and admin authentication and registration."""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from decorators.auth import load_user
from extensions import db
from models.auth import (
    LearnerProfile,
    Location,
    MentorProfile,
    MentorSkill,
    Role,
    Skill,
    User,
    VerificationDocument,
    LearnerSkill,
)
from services.security import issue_csrf_token
from services.uploads import save_upload


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def csrf_valid():
    return request.form.get("csrf_token") == session.get("csrf_token")


def role_for(name):
    role = Role.query.filter_by(name=name).first()
    if not role:
        role = Role(name=name)
        db.session.add(role)
        db.session.flush()
    return role


def location_for(city, area=None):
    city = (city or "").strip()
    area = (area or "").strip() or None
    location = Location.query.filter_by(city=city, area=area, country="Bangladesh").first()
    if not location:
        location = Location(city=city, area=area, country="Bangladesh")
        db.session.add(location)
        db.session.flush()
    return location


def common_fields():
    return {
        "full_name": request.form.get("full_name", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "phone": request.form.get("phone", "").strip(),
        "password": request.form.get("password", ""),
        "confirm_password": request.form.get("confirm_password", ""),
        "city": request.form.get("city", "").strip(),
        "area": request.form.get("area", "").strip(),
        "address": request.form.get("address", "").strip(),
    }


def validate_common(data):
    missing = [key for key in ("full_name", "email", "phone", "city", "address") if not data[key]]
    if missing:
        return "Please complete all required fields."
    if len(data["password"]) < 8:
        return "Password must be at least 8 characters."
    if data["password"] != data["confirm_password"]:
        return "Passwords do not match."
    if User.query.filter_by(email=data["email"]).first():
        return "An account with this email already exists."
    return None


def persist_documents(user, fields):
    uploads = [
        ("nid_document", "identity"),
        ("certificate", "certificate"),
        ("evidence_image", "evidence_image"),
        ("evidence_video", "evidence_video"),
    ]
    for field, category in uploads:
        file_info = save_upload(request.files.get(field), category)
        if file_info:
            db.session.add(VerificationDocument(user=user, document_type=category, **file_info))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not csrf_valid():
            flash("Your form expired. Please try again.", "danger")
            return render_template("auth/login.html")
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if not user or not user.check_password(request.form.get("password", "")):
            flash("Email or password is incorrect.", "danger")
        elif user.role.name == "Admin":
            flash("Use the dedicated admin login.", "warning")
        else:
            session.clear()
            session["user_id"] = user.id
            issue_csrf_token(session)
            if user.account_status != "Approved":
                return redirect(url_for("auth.account_status", status=user.account_status))
            next_url = request.args.get("next") or request.form.get("next")
            if next_url and next_url.startswith("/") and not next_url.startswith("//"):
                if "/api/" in next_url:
                    next_url = url_for("discovery.mentor_search")
                return redirect(next_url)
            return redirect(url_for("learner.dashboard" if user.role.name == "Learner" else "mentor.dashboard"))
    return render_template("auth/login.html")


@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if not csrf_valid():
            flash("Your form expired. Please try again.", "danger")
        else:
            user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
            if user and user.role.name == "Admin" and user.check_password(request.form.get("password", "")) and user.account_status == "Approved":
                session.clear()
                session["user_id"] = user.id
                issue_csrf_token(session)
                return redirect(url_for("admin.dashboard"))
            flash("Admin credentials are incorrect or inactive.", "danger")
    return render_template("auth/admin_login.html")


@auth_bp.route("/terms", methods=["GET", "POST"], endpoint="terms")
@auth_bp.route("/terms-and-regulations", methods=["GET", "POST"], endpoint="terms_and_regulations")
def terms():
    role = request.args.get("role") or request.form.get("role") or session.get("signup_role")
    if role:
        role = role.strip().lower()

    if role in {"learner", "mentor"}:
        if session.get("signup_role") != role:
            session["signup_role"] = role
            session["terms_accepted"] = False
    elif not session.get("signup_role"):
        flash("Please choose your account type first.", "info")
        return redirect(url_for("public.sign_up"))

    current_role = session.get("signup_role")

    if request.method == "POST":
        if not csrf_valid():
            flash("Your form expired. Please try again.", "danger")
            return redirect(url_for("auth.terms", role=current_role))

        if not request.form.get("agree_terms"):
            flash("Please accept the Terms & Regulations to continue.", "danger")
            return render_template("auth/terms.html", role=current_role)

        session["terms_accepted"] = True
        session["terms_version"] = "1.0"
        session["terms_accepted_at"] = datetime.utcnow().isoformat()

        if current_role == "learner":
            return redirect(url_for("auth.register_learner"))
        elif current_role == "mentor":
            return redirect(url_for("auth.register_mentor"))
        else:
            return redirect(url_for("public.sign_up"))

    return render_template("auth/terms.html", role=current_role)


@auth_bp.route("/register/learner", methods=["GET", "POST"])
def register_learner():
    if not session.get("terms_accepted") or session.get("signup_role") != "learner":
        flash("Please accept the Terms & Regulations to continue.", "warning")
        return redirect(url_for("auth.terms", role="learner"))

    data = common_fields()
    if request.method == "POST":
        if not csrf_valid():
            flash("Your form expired. Please try again.", "danger")
        elif (error := validate_common(data)):
            flash(error, "danger")
        elif not request.files.get("nid_document") or not request.files["nid_document"].filename:
            flash("An NID/Voter ID document is required.", "danger")
        else:
            try:
                user = User(
                    role=role_for("Learner"),
                    full_name=data["full_name"],
                    email=data["email"],
                    phone=data["phone"],
                    address=data["address"],
                    account_status="Pending",
                    location=location_for(data["city"], data["area"]),
                    terms_accepted=True,
                    terms_version=session.get("terms_version", "1.0"),
                    terms_accepted_at=datetime.utcnow(),
                )
                user.set_password(data["password"])
                profile_info = save_upload(request.files.get("profile_photo"), "profile")
                if profile_info:
                    user.profile_photo = profile_info["stored_name"]
                db.session.add(user)
                db.session.flush()
                learner_profile = LearnerProfile(user=user, bio="", interests=request.form.get("interests", "").strip())
                db.session.add(learner_profile)
                db.session.flush()
                persist_documents(user, data)
                db.session.commit()

                session.pop("terms_accepted", None)
                session.pop("terms_version", None)
                session.pop("terms_accepted_at", None)
                session.pop("signup_role", None)

                flash("Your learner application was submitted for admin approval.", "success")
                return redirect(url_for("auth.login"))
            except (ValueError, IntegrityError) as error:
                db.session.rollback()
                flash(str(error) if isinstance(error, ValueError) else "Unable to save this application.", "danger")
    return render_template("auth/register.html", role="Learner", data=data)


PREDEFINED_SKILLS = [
    "Programming / Coding",
    "Web Development",
    "App Development",
    "Graphic Design",
    "UI/UX Design",
    "Digital Marketing",
    "SEO",
    "Video Editing",
    "Photography",
    "Videography",
    "Microsoft Excel",
    "Microsoft Office",
    "Data Analysis",
    "English",
    "Public Speaking",
    "Content Writing",
    "Social Media Management",
    "Freelancing",
    "Guitar",
    "Piano / Keyboard",
    "Singing",
    "Drawing / Sketching",
    "Painting",
    "Cooking",
    "Baking",
    "Driving",
    "Cycling",
    "Swimming",
    "Fitness / Gym",
    "Language Learning",
]


def get_mentor_signup_skills():
    """Ensure all 30 predefined skills are available and return them ordered."""
    for name in PREDEFINED_SKILLS:
        existing = Skill.query.filter(func.lower(Skill.name) == name.lower()).first()
        if not existing:
            db.session.add(Skill(name=name, is_active=True))
        else:
            if existing.name != name:
                existing.name = name
            if not existing.is_active:
                existing.is_active = True
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    all_active = Skill.query.filter_by(is_active=True).all()
    rank_map = {name.lower(): i for i, name in enumerate(PREDEFINED_SKILLS)}
    return sorted(all_active, key=lambda s: (rank_map.get(s.name.lower(), 999), s.name.lower()))


@auth_bp.route("/register/mentor", methods=["GET", "POST"])
def register_mentor():
    if not session.get("terms_accepted") or session.get("signup_role") != "mentor":
        flash("Please accept the Terms & Regulations to continue.", "warning")
        return redirect(url_for("auth.terms", role="mentor"))

    data = common_fields()
    available_skills = get_mentor_signup_skills()
    selected_skill_ids = []

    if request.method == "POST":
        # Extract selected skill IDs from skill_ids list
        raw_ids = request.form.getlist("skill_ids")
        for val in raw_ids:
            for part in str(val).split(","):
                part = part.strip()
                if part.isdigit():
                    selected_skill_ids.append(int(part))

        # Fallback to skills text field if skill_ids was not passed
        if not selected_skill_ids and request.form.get("skills"):
            for item in request.form.get("skills", "").split(","):
                item = item.strip()
                if item.isdigit():
                    selected_skill_ids.append(int(item))
                elif item:
                    matched = Skill.query.filter(func.lower(Skill.name) == item.lower(), Skill.is_active.is_(True)).first()
                    if matched:
                        selected_skill_ids.append(matched.id)

        # Deduplicate while preserving order
        selected_skill_ids = list(dict.fromkeys(selected_skill_ids))

        # Server-side validation: must exist and be active
        valid_skills = (
            Skill.query.filter(Skill.id.in_(selected_skill_ids), Skill.is_active.is_(True)).all()
            if selected_skill_ids
            else []
        )

        if not csrf_valid():
            flash("Your form expired. Please try again.", "danger")
        elif (error := validate_common(data)):
            flash(error, "danger")
        elif not request.files.get("nid_document") or not request.files["nid_document"].filename:
            flash("An NID/Voter ID document is required.", "danger")
        elif not request.form.get("bio", "").strip() or not request.form.get("experience", "").strip() or not selected_skill_ids:
            flash("Bio, experience, and at least one skill are required.", "danger")
        elif not valid_skills:
            flash("Please select at least one valid skill from the list.", "danger")
        else:
            try:
                pricing = Decimal(request.form.get("pricing", "0") or "0")
                user = User(
                    role=role_for("Mentor"),
                    full_name=data["full_name"],
                    email=data["email"],
                    phone=data["phone"],
                    address=data["address"],
                    account_status="Pending",
                    location=location_for(data["city"], data["area"]),
                    terms_accepted=True,
                    terms_version=session.get("terms_version", "1.0"),
                    terms_accepted_at=datetime.utcnow(),
                )
                user.set_password(data["password"])
                profile_info = save_upload(request.files.get("profile_photo"), "profile")
                if profile_info:
                    user.profile_photo = profile_info["stored_name"]
                db.session.add(user)
                db.session.flush()

                mentor = MentorProfile(
                    user=user,
                    bio=request.form["bio"].strip(),
                    experience=request.form["experience"].strip(),
                    teaching_type=request.form.get("teaching_type", "In person").strip(),
                    is_paid=request.form.get("is_paid") == "paid",
                    pricing=pricing,
                )
                db.session.add(mentor)
                db.session.flush()

                for skill in valid_skills:
                    db.session.add(
                        MentorSkill(
                            mentor_profile=mentor,
                            skill=skill,
                            experience=request.form.get("experience", "").strip(),
                            is_paid=request.form.get("is_paid") == "paid",
                            price=pricing,
                            pricing_type=request.form.get("pricing_type", "Course-based"),
                        )
                    )

                persist_documents(user, data)
                db.session.commit()

                session.pop("terms_accepted", None)
                session.pop("terms_version", None)
                session.pop("terms_accepted_at", None)
                session.pop("signup_role", None)

                flash("Your mentor application was submitted for admin approval.", "success")
                return redirect(url_for("auth.login"))
            except (ValueError, InvalidOperation, IntegrityError) as error:
                db.session.rollback()
                flash(str(error) if isinstance(error, (ValueError, InvalidOperation)) else "Unable to save this application.", "danger")

    return render_template(
        "auth/register.html",
        role="Mentor",
        data=data,
        skills=available_skills,
        selected_skill_ids=selected_skill_ids,
    )


@auth_bp.get("/status/<status>")
def account_status(status):
    latest_notification = None
    user = getattr(g, "current_user", None)
    if user:
        from models.connection import Notification
        latest_notification = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).first()
    return render_template("auth/status.html", status=status, latest_notification=latest_notification)


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("public.home"))
