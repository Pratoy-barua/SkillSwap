"""Learner and mentor dashboards and profile editing."""

from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from decorators.auth import role_required
from extensions import db
from models.auth import LearnerProfile, LearnerSkill, MentorSkill, Skill
from models.connection import LearningRelationship, LearningRequest, Notification
from models.learning import Payment
from models.reviews import Review
from models.store import Order
from services.security import issue_csrf_token
from services.uploads import save_upload


learner_bp = Blueprint("learner", __name__, url_prefix="/learner")
mentor_bp = Blueprint("mentor", __name__, url_prefix="/mentor")


def valid_csrf():
    from flask import session

    return request.form.get("csrf_token") == session.get("csrf_token")


# ============================================================
# LEARNER DASHBOARD
# ============================================================

@learner_bp.get("/dashboard")
@role_required("Learner")
def dashboard():
    user_id = g.current_user.id
    active_relationships = LearningRelationship.query.filter_by(learner_id=user_id, status="Active").order_by(LearningRelationship.updated_at.desc()).limit(3).all()
    recent_requests = LearningRequest.query.filter_by(learner_id=user_id).order_by(LearningRequest.created_at.desc()).limit(4).all()
    recent_notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(4).all()
    recent_orders = Order.query.filter_by(buyer_id=user_id).order_by(Order.created_at.desc()).limit(5).all()
    return render_template(
        "learner/dashboard.html",
        profile=g.current_user.learner_profile,
        active_relationships=active_relationships,
        recent_requests=recent_requests,
        recent_notifications=recent_notifications,
        recent_orders=recent_orders,
        pending_requests=LearningRequest.query.filter_by(learner_id=user_id, status="Pending").count(),
        relationships=LearningRelationship.query.filter_by(learner_id=user_id, status="Active").count(),
        completed_learning=LearningRelationship.query.filter_by(learner_id=user_id, status="Completed").count(),
        unread_notifications=Notification.query.filter_by(user_id=user_id, is_read=False).all(),
    )


# ============================================================
# LEARNER INTERESTS
# ============================================================

@learner_bp.route("/interests", methods=["GET", "POST"])
@role_required("Learner")
def interests():
    profile = g.current_user.learner_profile

    if request.method == "POST":
        selected = {
            int(value)
            for value in request.form.getlist("skill_ids")
        }

        profile.skills.clear()

        skills = (
            Skill.query
            .filter(
                Skill.id.in_(selected),
                Skill.is_active.is_(True)
            )
            .all()
            if selected
            else []
        )

        for skill in skills:
            profile.skills.append(
                LearnerSkill(skill=skill)
            )

        profile.interests = ", ".join(
            skill.skill.name
            for skill in profile.skills
        )

        db.session.commit()

        flash(
            "Learning interests updated.",
            "success"
        )

        return redirect(
            url_for("learner.interests")
        )

    return render_template(
        "learner/interests.html",
        profile=profile,
        skills=(
            Skill.query
            .filter_by(is_active=True)
            .order_by(Skill.name)
            .all()
        )
    )


# ============================================================
# LEARNER PROFILE
# ============================================================

@learner_bp.route("/profile", methods=["GET", "POST"])
@role_required("Learner")
def profile():
    profile = g.current_user.learner_profile

    if request.method == "POST":

        if not valid_csrf():
            flash(
                "Your form expired. Please try again.",
                "danger"
            )

        else:
            g.current_user.full_name = (
                request.form.get("full_name", "").strip()
                or g.current_user.full_name
            )

            g.current_user.phone = (
                request.form.get("phone", "").strip()
                or g.current_user.phone
            )

            g.current_user.address = (
                request.form.get("address", "").strip()
                or g.current_user.address
            )

            profile.bio = (
                request.form.get("bio", "").strip()
            )

            profile.interests = (
                request.form.get("interests", "").strip()
            )

            # Professional details
            profile.occupation = request.form.get("occupation", "").strip() or None
            profile.gender = request.form.get("gender", "").strip() or None
            profile.linkedin_url = request.form.get("linkedin_url", "").strip() or None
            profile.github_url = request.form.get("github_url", "").strip() or None
            profile.website_url = request.form.get("website_url", "").strip() or None

            dob_str = request.form.get("date_of_birth", "").strip()
            if dob_str:
                from datetime import date as _date
                try:
                    profile.date_of_birth = _date.fromisoformat(dob_str)
                except ValueError:
                    pass
            else:
                profile.date_of_birth = None

            # Update location
            if request.form.get("city", "").strip():
                from routes.auth import location_for

                g.current_user.location = location_for(
                    request.form["city"],
                    request.form.get("area")
                )

            # Profile photo upload
            if (
                request.files.get("profile_photo")
                and request.files["profile_photo"].filename
            ):
                try:
                    g.current_user.profile_photo = (
                        save_upload(
                            request.files["profile_photo"],
                            "profile"
                        )["stored_name"]
                    )

                except ValueError as error:
                    flash(
                        str(error),
                        "danger"
                    )

            db.session.commit()

            flash(
                "Your learner profile was updated.",
                "success"
            )

            return redirect(
                url_for("learner.profile")
            )

    return render_template(
        "learner/profile.html",
        profile=profile
    )


# ============================================================
# MENTOR DASHBOARD
# ============================================================

@mentor_bp.get("/dashboard")
@role_required("Mentor")
def dashboard():
    user_id = g.current_user.id
    active_relationships = LearningRelationship.query.filter_by(mentor_id=user_id, status="Active").order_by(LearningRelationship.updated_at.desc()).limit(4).all()
    pending_items = LearningRequest.query.filter_by(mentor_id=user_id, status="Pending").order_by(LearningRequest.created_at.desc()).limit(4).all()
    recent_notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).limit(4).all()
    recent_reviews = Review.query.filter_by(mentor_id=user_id).order_by(Review.created_at.desc()).limit(3).all()
    successful_payments = Payment.query.filter_by(mentor_id=user_id, status="Successful").all()
    recent_orders = Order.query.filter_by(buyer_id=user_id).order_by(Order.created_at.desc()).limit(5).all()
    return render_template(
        "mentor/dashboard.html",
        profile=g.current_user.mentor_profile,
        active_relationships=active_relationships,
        pending_items=pending_items,
        recent_notifications=recent_notifications,
        recent_reviews=recent_reviews,
        recent_orders=recent_orders,
        pending_requests=LearningRequest.query.filter_by(mentor_id=user_id, status="Pending").count(),
        relationships=LearningRelationship.query.filter_by(mentor_id=user_id, status="Active").count(),
        completed_learning=LearningRelationship.query.filter_by(mentor_id=user_id, status="Completed").count(),
        total_earnings=sum((item.mentor_earning for item in successful_payments), 0),
        unread_notifications=Notification.query.filter_by(user_id=user_id, is_read=False).all(),
    )


# ============================================================
# MENTOR SKILLS
# ============================================================

@mentor_bp.route("/skills", methods=["GET", "POST"])
@role_required("Mentor")
def skills():
    profile = g.current_user.mentor_profile

    if request.method == "POST":

        selected = {
            int(value)
            for value in request.form.getlist("skill_ids")
        }

        profile.skills.clear()

        skills = (
            Skill.query
            .filter(
                Skill.id.in_(selected),
                Skill.is_active.is_(True)
            )
            .all()
            if selected
            else []
        )

        for skill in skills:
            profile.skills.append(
                MentorSkill(
                    skill=skill,
                    experience=profile.experience,
                    is_paid=profile.is_paid,
                    price=profile.pricing,
                    pricing_type=request.form.get(
                        "pricing_type",
                        "Course-based"
                    )
                )
            )

        db.session.commit()

        flash(
            "Teaching skills updated.",
            "success"
        )

        return redirect(
            url_for("mentor.skills")
        )

    return render_template(
        "mentor/skills.html",
        profile=profile,
        skills=(
            Skill.query
            .filter_by(is_active=True)
            .order_by(Skill.name)
            .all()
        )
    )


# ============================================================
# MENTOR PROFILE
# ============================================================

@mentor_bp.route("/profile", methods=["GET", "POST"])
@role_required("Mentor")
def profile():
    profile = g.current_user.mentor_profile

    if request.method == "POST":

        if not valid_csrf():
            flash(
                "Your form expired. Please try again.",
                "danger"
            )

        else:
            g.current_user.full_name = (
                request.form.get("full_name", "").strip()
                or g.current_user.full_name
            )

            g.current_user.phone = (
                request.form.get("phone", "").strip()
                or g.current_user.phone
            )

            g.current_user.address = (
                request.form.get("address", "").strip()
                or g.current_user.address
            )

            profile.bio = (
                request.form.get("bio", "").strip()
            )

            profile.experience = (
                request.form.get("experience", "").strip()
            )

            profile.teaching_type = (
                request.form.get("teaching_type", "").strip()
            )

            profile.is_paid = (
                request.form.get("is_paid") == "paid"
            )

            # Professional details
            profile.occupation = request.form.get("occupation", "").strip() or None
            profile.gender = request.form.get("gender", "").strip() or None
            profile.linkedin_url = request.form.get("linkedin_url", "").strip() or None
            profile.github_url = request.form.get("github_url", "").strip() or None
            profile.website_url = request.form.get("website_url", "").strip() or None

            dob_str = request.form.get("date_of_birth", "").strip()
            if dob_str:
                from datetime import date as _date
                try:
                    profile.date_of_birth = _date.fromisoformat(dob_str)
                except ValueError:
                    pass
            else:
                profile.date_of_birth = None

            # Get skills from comma-separated input
            names = {
                item.strip().lower()
                for item in request.form.get(
                    "skills",
                    ""
                ).split(",")
                if item.strip()
            }

            profile.skills.clear()

            for name in names:

                skill = (
                    Skill.query
                    .filter_by(name=name)
                    .first()
                )

                if not skill:
                    skill = Skill(name=name)
                    db.session.add(skill)
                    db.session.flush()

                profile.skills.append(
                    MentorSkill(
                        skill=skill,
                        experience=profile.experience,
                        is_paid=profile.is_paid,
                        price=profile.pricing,
                        pricing_type=request.form.get(
                            "pricing_type",
                            "Course-based"
                        )
                    )
                )

            # Validate pricing
            try:
                profile.pricing = Decimal(
                    request.form.get(
                        "pricing",
                        "0"
                    ) or "0"
                )

            except InvalidOperation:
                flash(
                    "Pricing must be a valid number.",
                    "danger"
                )

                return render_template(
                    "mentor/profile.html",
                    profile=profile
                )

            # Update location
            if request.form.get("city", "").strip():
                from routes.auth import location_for

                g.current_user.location = location_for(
                    request.form["city"],
                    request.form.get("area")
                )

            # Profile photo upload
            if (
                request.files.get("profile_photo")
                and request.files["profile_photo"].filename
            ):
                try:
                    g.current_user.profile_photo = (
                        save_upload(
                            request.files["profile_photo"],
                            "profile"
                        )["stored_name"]
                    )

                except ValueError as error:
                    flash(
                        str(error),
                        "danger"
                    )

            db.session.commit()

            flash(
                "Your mentor profile was updated.",
                "success"
            )

            return redirect(
                url_for("mentor.profile")
            )

    return render_template(
        "mentor/profile.html",
        profile=profile
    )
