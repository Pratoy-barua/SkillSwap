"""Learner reviews and admin moderation."""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from decorators.auth import role_required
from extensions import db
from models.connection import LearningRelationship
from models.reviews import Review
from services.notifications import notify

reviews_bp = Blueprint("reviews", __name__)


@reviews_bp.route("/learner/reviews/<int:relationship_id>", methods=["GET", "POST"])
@role_required("Learner")
def learner_review(relationship_id):
    relationship = LearningRelationship.query.filter_by(id=relationship_id, learner_id=g.current_user.id, status="Completed").first_or_404()
    review = Review.query.filter_by(relationship_id=relationship.id).first()
    if request.method == "POST":
        try:
            rating = int(request.form.get("rating", "0"))
        except ValueError:
            rating = 0
        if rating not in range(1, 6):
            flash("Choose a rating from 1 to 5.", "danger")
            return render_template("reviews/form.html", relationship=relationship, review=review)
        if not review:
            review = Review(learner_id=g.current_user.id, mentor_id=relationship.mentor_id, relationship_id=relationship.id, skill_id=relationship.skill_id)
            db.session.add(review)
        review.rating = rating
        review.review_text = request.form.get("review_text", "").strip()[:4000]
        review.status = "Published"
        db.session.flush()
        average = db.session.query(func.avg(Review.rating)).filter_by(mentor_id=relationship.mentor_id, status="Published").scalar()
        if relationship.mentor.mentor_profile:
            relationship.mentor.mentor_profile.rating = average or 0
        notify(relationship.mentor_id, "review_received", "New learner review", f"{g.current_user.full_name} left a {rating}/5 review.", "review", review.id)
        db.session.commit()
        flash("Your review has been published.", "success")
        return redirect(url_for("connections.learner_mentors"))
    return render_template("reviews/form.html", relationship=relationship, review=review)


@reviews_bp.get("/mentor/reviews")
@role_required("Mentor")
def mentor_reviews():
    records = Review.query.filter_by(mentor_id=g.current_user.id).order_by(Review.created_at.desc()).all()
    average = db.session.query(func.avg(Review.rating)).filter_by(mentor_id=g.current_user.id, status="Published").scalar()
    return render_template("reviews/mentor.html", reviews=records, average=average or 0)


@reviews_bp.get("/admin/reviews")
@role_required("Admin")
def admin_reviews():
    return render_template("admin/reviews.html", reviews=Review.query.order_by(Review.created_at.desc()).all())


@reviews_bp.post("/admin/reviews/<int:review_id>/<action>")
@role_required("Admin")
def moderate_review(review_id, action):
    review = Review.query.get_or_404(review_id)
    statuses = {"publish": "Published", "hide": "Hidden", "flag": "Flagged"}
    if action not in statuses:
        abort(404)
    review.status = statuses[action]
    average = db.session.query(func.avg(Review.rating)).filter_by(mentor_id=review.mentor_id, status="Published").scalar()
    if review.mentor and review.mentor.mentor_profile:
        review.mentor.mentor_profile.rating = average or 0
    db.session.commit()
    flash(f"Review marked {review.status.lower()}.", "success")
    return redirect(url_for("reviews.admin_reviews"))
