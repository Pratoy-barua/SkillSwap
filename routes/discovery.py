"""Dynamic skills catalogue, mentor search, and public mentor profiles."""

from sqlalchemy import and_, func, or_
from flask import Blueprint, flash, g, jsonify, render_template, request, url_for
from extensions import db

from decorators.auth import login_required
from models.auth import Location, MentorProfile, MentorSkill, Role, Skill, User
from models.connection import Conversation, LearningRelationship
from models.learning import MentorProfileAccess
from models.reviews import Review
from services.ai_recommendation import get_ai_recommendations
from services.payments import get_mentor_unlock_fee
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


class MaskedMentorProfile:
    """Wrapper that prevents URL leaks when details are locked while keeping relationships functional."""
    def __init__(self, real_profile, can_view):
        self._real = real_profile
        self._can_view = can_view

    @property
    def linkedin_url(self):
        return self._real.linkedin_url if self._can_view else None

    @property
    def github_url(self):
        return self._real.github_url if self._can_view else None

    @property
    def website_url(self):
        return self._real.website_url if self._can_view else None

    def __getattr__(self, item):
        return getattr(self._real, item)


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
    rating = float(db.session.query(func.avg(Review.rating)).filter_by(mentor_id=mentor.id, status="Published").scalar() or 0)
    review_count = Review.query.filter_by(mentor_id=mentor.id, status="Published").count()
    recent_reviews = Review.query.filter_by(mentor_id=mentor.id, status="Published").order_by(Review.created_at.desc()).limit(10).all()

    # Permission check for paid contact details
    current_user = getattr(g, "current_user", None)
    can_view_details = False
    is_owner = False
    is_admin = False

    if current_user:
        if current_user.id == mentor.id:
            can_view_details = True
            is_owner = True
        elif current_user.role.name == "Admin":
            can_view_details = True
            is_admin = True
        elif current_user.role.name == "Learner":
            access = MentorProfileAccess.query.filter_by(learner_id=current_user.id, mentor_id=mentor.id).first()
            if access:
                can_view_details = True

    unlock_fee = get_mentor_unlock_fee(db.session)

    raw_profile = mentor.mentor_profile
    has_linkedin = bool(raw_profile and raw_profile.linkedin_url and raw_profile.linkedin_url.strip())
    has_github = bool(raw_profile and raw_profile.github_url and raw_profile.github_url.strip())
    has_website = bool(raw_profile and raw_profile.website_url and raw_profile.website_url.strip())
    has_any_contact = has_linkedin or has_github or has_website

    if raw_profile:
        mentor.mentor_profile = MaskedMentorProfile(raw_profile, can_view_details)

    return render_template(
        "mentor/public_profile.html",
        mentor=mentor,
        active_relationship=active_relationship,
        rating=rating,
        review_count=review_count,
        recent_reviews=recent_reviews,
        can_view_details=can_view_details,
        is_owner=is_owner,
        is_admin=is_admin,
        unlock_fee=unlock_fee,
        has_linkedin=has_linkedin,
        has_github=has_github,
        has_website=has_website,
        has_any_contact=has_any_contact,
    )


@discovery_bp.route("/api/ai-recommend", methods=["GET", "POST"])
@login_required
def api_ai_recommend():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
    else:
        data = request.args.to_dict()

    try:
        learner_lat = float(data.get("latitude"))
        learner_lon = float(data.get("longitude"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valid latitude and longitude coordinates are required."}), 400

    requested_skill_id = data.get("skill_id")
    if requested_skill_id:
        try:
            requested_skill_id = int(requested_skill_id)
        except (TypeError, ValueError):
            requested_skill_id = None
    elif data.get("skill_name") or data.get("skill"):
        s_name = (data.get("skill_name") or data.get("skill")).strip()
        matched_skill_obj = Skill.query.filter(func.lower(Skill.name) == s_name.lower(), Skill.is_active.is_(True)).first()
        if matched_skill_obj:
            requested_skill_id = matched_skill_obj.id

    max_price = data.get("max_price")
    if max_price is not None and str(max_price).strip() != "":
        try:
            max_price = float(max_price)
        except (TypeError, ValueError):
            max_price = None
    else:
        max_price = None

    preference = data.get("preference") or data.get("is_paid")
    if preference not in ("free", "paid"):
        preference = None

    KNOWN_COORDINATES = {
        ("dhaka", "farmgate"): (23.7561, 90.3872),
        ("dhaka", "notunbazar"): (23.7979, 90.4236),
        ("dhaka", "gulshan"): (23.7925, 90.4078),
        ("dhaka", "banani"): (23.7937, 90.4043),
        ("dhaka", "dhanmondi"): (23.7461, 90.3742),
        ("dhaka", "uttara"): (23.8759, 90.3795),
        ("dhaka", "mirpur"): (23.8223, 90.3654),
        ("dhaka", "mohakhali"): (23.7777, 90.4005),
        ("dhaka", "shahbagh"): (23.7380, 90.3958),
        ("dhaka", None): (23.8103, 90.4125),
        ("rajshahi", "shahebbazar"): (24.3636, 88.6042),
        ("rajshahi", None): (24.3745, 88.6042),
        ("chittagong", None): (22.3569, 91.7832),
        ("sylhet", None): (24.8949, 91.8687),
        ("khulna", None): (22.8456, 89.5403),
        ("barisal", None): (22.7010, 90.3535),
        ("rangpur", None): (25.7439, 89.2752),
        ("mymensingh", None): (24.7471, 90.4203),
    }

    approved_mentors = (
        User.query.join(User.role)
        .join(User.mentor_profile)
        .join(User.location)
        .filter(Role.name == "Mentor", User.account_status == "Approved")
        .all()
    )

    mentors_data = []
    for u in approved_mentors:
        mp = u.mentor_profile
        loc = u.location
        if not loc:
            continue

        if loc.latitude is None or loc.longitude is None:
            c_key = loc.city.strip().lower() if loc.city else ""
            a_key = loc.area.strip().lower() if loc.area else None
            resolved = KNOWN_COORDINATES.get((c_key, a_key)) or KNOWN_COORDINATES.get((c_key, None))
            if resolved:
                loc.latitude = resolved[0]
                loc.longitude = resolved[1]
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
            else:
                continue


        skills_info = []
        for ms in mp.skills:
            if ms.skill and ms.skill.is_active:
                skills_info.append({
                    "skill_id": ms.skill_id,
                    "skill_name": ms.skill.name,
                    "price": float(ms.price or 0.0),
                    "is_paid": ms.is_paid,
                    "experience": ms.experience or mp.experience
                })

        if not skills_info:
            continue

        # If a specific skill is requested, filter out mentors that do not teach that skill
        if requested_skill_id:
            matching = [s for s in skills_info if s["skill_id"] == requested_skill_id]
            if not matching:
                continue
            primary_skill = matching[0]["skill_name"]
            primary_price = matching[0]["price"]
            is_paid = matching[0]["is_paid"]
            primary_exp = matching[0]["experience"]
        else:
            primary_skill = skills_info[0]["skill_name"]
            primary_price = skills_info[0]["price"]
            is_paid = skills_info[0]["is_paid"]
            primary_exp = skills_info[0]["experience"]

        avatar_url = None
        if u.profile_photo:
            avatar_url = url_for("static", filename="uploads/public/" + u.profile_photo)

        mentors_data.append({
            "user_id": u.id,
            "full_name": u.full_name,
            "profile_photo": u.profile_photo,
            "avatar_url": avatar_url,
            "bio": mp.bio,
            "teaching_type": mp.teaching_type,
            "experience": primary_exp,
            "rating": float(mp.rating or 0.0),
            "city": loc.city,
            "area": loc.area or loc.city,
            "latitude": float(loc.latitude),
            "longitude": float(loc.longitude),
            "skill_name": primary_skill,
            "price": primary_price,
            "is_paid": is_paid,
            "skills": skills_info,
            "profile_url": url_for("discovery.mentor_profile", user_id=u.id)
        })

    recommendations = get_ai_recommendations(
        learner_lat=learner_lat,
        learner_lon=learner_lon,
        mentors_data=mentors_data,
        requested_skill_id=requested_skill_id,
        max_price=max_price,
        preference=preference
    )

    return jsonify(recommendations)

