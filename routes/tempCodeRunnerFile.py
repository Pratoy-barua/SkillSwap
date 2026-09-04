"""Learner, mentor, and admin authentication and registration."""

from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
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


def skill_names(raw):
    return {item.strip().lower() for item in (raw or "").split(",") if item.strip()}


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


@auth_bp.route("/register/learner", methods=["GET", "POST"])
def register_learner():
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
                user = User(role=role_for("Learner"), full_name=data["full_name"], email=data["email"], phone=data["phone"], address=data["address"], account_status="Pending", location=location_for(data["city"], data["area"]))
                user.set_password(data["password"])
                profile_info = save_upload(request.files.get("profile_photo"), "profile")
                if profile_info:
                    user.profile_photo = profile_info["stored_name"]
                db.session.add(user)
                db.session.flush()
                learner_profile = LearnerProfile(user=user, bio="", interests=request.form.get("interests", "").strip())
                db.session.add(learner_profile)
                db.session.flush()
                for name in skill_names(request.form.get("interests")):
                    skill = Skill.query.filter_by(name=name).first() or Skill(name=name, is_active=True)
                    db.session.add(skill)
                    db.session.flush()
                    db.session.add(LearnerSkill(learner_profile=learner_profile, skill=skill))
                persist_documents(user, data)
                db.session.commit()
                flash("Your learner application was submitted for admin approval.", "success")
                return redirect(url_for("auth.login"))
            except (ValueError, IntegrityError) as error:
                db.session.rollback()
                flash(str(error) if isinstance(error, ValueError) else "Unable to save this application.", "danger")
    return render_template("auth/register.html", role="Learner", data=data)


@auth_bp.route("/register/mentor", methods=["GET", "POST"])
def register_mentor():
    data = common_fields()
    if request.method == "POST":
        if not csrf_valid():
            flash("Your form expired. Please try again.", "danger")
        elif (error := validate_common(data)):
            flash(error, "danger")
        elif not request.files.get("nid_document") or not request.files["nid_document"].filename:
            flash("An NID/Voter ID document is required.", "danger")
        elif not request.form.get("bio", "").strip() or not request.form.get("experience", "").strip() or not request.form.get("skills", "").strip():
            flash("Bio, experience, and at least one skill are required.", "danger")
        else:
            try:
                pricing = Decimal(request.form.get("pricing", "0") or "0")
                user = User(role=role_for("Mentor"), full_name=data["full_name"], email=data["email"], phone=data["phone"], address=data["address"], account_status="Pending", location=location_for(data["city"], data["area"]))
                user.set_password(data["password"])
                profile_info = save_upload(request.files.get("profile_photo"), "profile")
                if profile_info:
                    user.profile_photo = profile_info["stored_name"]
                db.session.add(user)
                db.session.flush()
                mentor = MentorProfile(user=user, bio=request.form["bio"].strip(), experience=request.form["experience"].strip(), teaching_type=request.form.get("teaching_type", "In person").strip(), is_paid=request.form.get("is_paid") == "paid", pricing=pricing)
                db.session.add(mentor)
                for name in {item.strip().lower() for item in request.form["skills"].split(",") if item.strip()}:
                    skill = Skill.query.filter_by(name=name).first() or Skill(name=name)
                    db.session.add(skill)
                    db.session.flush()
                    db.session.add(MentorSkill(mentor_profile=mentor, skill=skill, experience=request.form.get("experience", "").strip(), is_paid=request.form.get("is_paid") == "paid", price=pricing, pricing_type=request.form.get("pricing_type", "Course-based")))
                persist_documents(user, data)
                db.session.commit()
                flash("Your mentor application was submitted for admin approval.", "success")
                return redirect(url_for("auth.login"))
            except (ValueError, InvalidOperation, IntegrityError) as error:
                db.session.rollback()
                flash(str(error) if isinstance(error, (ValueError, InvalidOperation)) else "Unable to save this application.", "danger")
    return render_template("auth/register.html", role="Mentor", data=data)


@auth_bp.get("/status/<status>")
def account_status(status):
    return render_template("auth/status.html", status=status)


@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("public.home"))