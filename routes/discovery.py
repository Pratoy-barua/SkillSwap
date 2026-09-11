"""Dynamic skills catalogue, mentor search, and public mentor profiles."""

from sqlalchemy import and_, func, or_
from flask import Blueprint, flash, g, render_template, request, url_for
from extensions import db

from models.auth import Location, MentorProfile, MentorSkill, Role, Skill, User
from models.connection import Conversation, LearningRelationship
from models.reviews import Review
from services.premium import has_premium


discovery_bp = Blueprint("discovery", __name__)


def active_skills():
    try:
        return Skill.query.filter_by(is_active=True).order_by(Skill.name.asc()).all()
    except Exception:
        return []


def mentor_skill_query():
    return (
        MentorSkill.query.join(MentorSkill.mentor_profile)
        .join(MentorProfile.user)
        .join(User.role)
        .join(User.location)
        .join(MentorSkill.skill)
        .filter(User.account_status == "Approved", Role.name == "Mentor", Skill.is_active.is_(True))
    )


@discovery_bp.get("/skills")
def skills():
    results = []
    for skill in active_skills():
        count = mentor_skill_query().filter(MentorSkill.skill_id == skill.id).count()
        results.append((skill, count))
    return render_template("skills/index.html", skills=results)


@discovery_bp.get("/mentors")
def mentor_search():
    if request.args.get("advanced") == "1" and (not g.current_user or not has_premium(g.current_user.id)):
        flash("Advanced mentor filters are available with an active Premium plan.", "warning")
        return render_template("skills/search.html", matches=[], skills=active_skills(), locations=[], filters=request.args, selected_skill_id=request.args.get("skill_id", type=int), premium_required=True)
    skill_id = request.args.get("skill_id", type=int)
    city = request.args.get("city", "").strip()
    area = request.args.get("area", "").strip()
    is_paid = request.args.get("is_paid", "")
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    experience = request.args.get("experience", "").strip()
    min_rating = request.args.get("min_rating", type=float)

    query = mentor_skill_query()
    if skill_id:
        query = query.filter(MentorSkill.skill_id == skill_id)
    if city:
        query = query.filter(func.lower(Location.city) == city.lower())
    if area:
        query = query.filter(func.lower(Location.area) == area.lower())
    if is_paid == "free":
        query = query.filter(MentorSkill.is_paid.is_(False))
    elif is_paid == "paid":
        query = query.filter(MentorSkill.is_paid.is_(True))
    if min_price is not None:
        query = query.filter(MentorSkill.price >= min_price)
    if max_price is not None:
        query = query.filter(MentorSkill.price <= max_price)
    if experience:
        query = query.filter(func.lower(MentorSkill.experience).like(f"%{experience.lower()}%"))
    if min_rating is not None:
        query = query.filter(MentorProfile.rating >= min_rating)
    matches = query.order_by(User.full_name.asc()).all()
    locations = Location.query.join(User, User.location_id == Location.id).join(User.role).filter(Role.name == "Mentor", User.account_status == "Approved").distinct().order_by(Location.city, Location.area).all()
    return render_template("skills/search.html", matches=matches, skills=active_skills(), locations=locations, filters=request.args, selected_skill_id=skill_id)


@discovery_bp.get("/mentor/<int:user_id>")
def mentor_profile(user_id):
    mentor = (
        User.query.join(User.role)
        .filter(User.id == user_id, Role.name == "Mentor", User.account_status == "Approved")
        .first_or_404()
    )
    active_relationship = None
    if getattr(g, "current_user", None) and g.current_user.role.name == "Learner":
        active_relationship = LearningRelationship.query.filter_by(learner_id=g.current_user.id, mentor_id=mentor.id, status="Active").first()
        if active_relationship and not active_relationship.conversation:
            active_relationship.conversation = Conversation(relationship=active_relationship)
            db.session.commit()
    rating = db.session.query(func.avg(Review.rating)).filter_by(mentor_id=mentor.id, status="Published").scalar() or 0
    review_count = Review.query.filter_by(mentor_id=mentor.id, status="Published").count()
    recent_reviews = Review.query.filter_by(mentor_id=mentor.id, status="Published").order_by(Review.created_at.desc()).limit(5).all()
    return render_template("mentor/public_profile.html", mentor=mentor, active_relationship=active_relationship, rating=rating, review_count=review_count, recent_reviews=recent_reviews)
