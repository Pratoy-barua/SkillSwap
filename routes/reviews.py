"""Learner reviews and admin moderation."""

from decimal import Decimal
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from decorators.auth import role_required
from extensions import db
from models.auth import MentorProfile
from models.connection import LearningRelationship
from models.reviews import Review
from services.notifications import notify

reviews_bp = Blueprint("reviews", __name__)


def recalculate_mentor_rating(mentor_id):
    """Recalculate and synchronize MentorProfile.rating from published reviews."""
    average = db.session.query(func.avg(Review.rating)).filter_by(mentor_id=mentor_id, status="Published").scalar()
    mentor_profile = MentorProfile.query.filter_by(user_id=mentor_id).first()
    if mentor_profile:
        mentor_profile.rating = round(Decimal(str(average or 0)), 2) if average else Decimal("0.00")


@reviews_bp.route("/learner/reviews/<int:relationship_id>", methods=["GET", "POST"])
@role_required("Learner")
def learner_review(relationship_id):
    relationship = LearningRelationship.query.filter(
        LearningRelationship.id == relationship_id,
        LearningRelationship.learner_id == g.current_user.id,
        LearningRelationship.status.in_(["Active", "Completed"]),
    ).first_or_404()
    review = Review.query.filter_by(relationship_id=relationship.id).first()

    if request.method == "POST":
        try:
            rating = int(request.form.get("rating", "0"))
        except (ValueError, TypeError):
            rating = 0

        if rating not in range(1, 6):
            flash("Please choose a rating from 1 to 5 stars.", "danger")
            return redirect(url_for("learning.progress", relationship_id=relationship.id))

        review_text = (request.form.get("review_text") or "").strip()[:4000]
        is_new = review is None

        if is_new:
            review = Review(
                learner_id=g.current_user.id,
                mentor_id=relationship.mentor_id,
                relationship_id=relationship.id,
                skill_id=relationship.skill_id,
                rating=rating,
                review_text=review_text,
                status="Published",
            )
            db.session.add(review)
        else:
            review.rating = rating
            review.review_text = review_text
            review.status = "Published"

        db.session.flush()
        recalculate_mentor_rating(relationship.mentor_id)

        if is_new:
            notify(relationship.mentor_id, "review_received", "New learner review", f"{g.current_user.full_name} left a {rating}/5 review.", "review", review.id)
            flash("Your review has been submitted successfully.", "success")
        else:
            notify(relationship.mentor_id, "review_updated", "Review updated", f"{g.current_user.full_name} updated their review to {rating}/5.", "review", review.id)
            flash("Your review has been updated successfully.", "success")

        db.session.commit()
        return redirect(url_for("learning.progress", relationship_id=relationship.id))

    return render_template("reviews/form.html", relationship=relationship, review=review)


@reviews_bp.post("/learner/reviews/<int:relationship_id>/delete")
@role_required("Learner")
def delete_review(relationship_id):
    relationship = LearningRelationship.query.filter(
        LearningRelationship.id == relationship_id,
        LearningRelationship.learner_id == g.current_user.id,
        LearningRelationship.status.in_(["Active", "Completed"]),
    ).first_or_404()
    review = Review.query.filter_by(relationship_id=relationship.id, learner_id=g.current_user.id).first_or_404()
    mentor_id = review.mentor_id

    db.session.delete(review)
    db.session.flush()
    recalculate_mentor_rating(mentor_id)
    db.session.commit()

    flash("Your review has been deleted.", "success")
    return redirect(url_for("learning.progress", relationship_id=relationship.id))


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
    db.session.flush()
    recalculate_mentor_rating(review.mentor_id)
    db.session.commit()
    flash(f"Review marked {review.status.lower()}.", "success")
    return redirect(url_for("reviews.admin_reviews"))
