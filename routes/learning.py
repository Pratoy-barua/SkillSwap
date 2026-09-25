"""Mentor learning-plan and progress management."""

from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from decorators.auth import role_required
from extensions import db
from models.connection import LearningRelationship, Notification
from models.learning import LearningPlan, LearningProgress
from models.reviews import Review
from services.notifications import notify


learning_bp = Blueprint("learning", __name__)
ALLOWED_PROGRESS = {0, 25, 50, 75, 100}


def owned_relationship(relationship_id, role):
    key = "mentor_id" if role == "Mentor" else "learner_id"
    return LearningRelationship.query.filter_by(id=relationship_id, **{key: g.current_user.id}, status="Active").first_or_404()


@learning_bp.route("/mentor/learning/<int:relationship_id>/plan", methods=["GET", "POST"])
@role_required("Mentor")
def plan(relationship_id):
    relationship = owned_relationship(relationship_id, "Mentor")
    item = relationship.plan
    if request.method == "POST":
        try:
            pricing = Decimal(request.form.get("pricing", "0") or "0")
        except InvalidOperation:
            flash("Pricing must be a valid number.", "danger")
            return render_template("learning/plan.html", relationship=relationship, plan=item)
        start = request.form.get("start_date") or date.today().isoformat()
        expected = request.form.get("expected_completion_date") or None
        if not item:
            item = LearningPlan(relationship=relationship)
            db.session.add(item)
        item.title = request.form.get("title", "").strip()[:180]
        item.description = request.form.get("description", "").strip()
        item.pricing = pricing
        item.pricing_type = request.form.get("pricing_type", "Course-based")
        item.start_date = date.fromisoformat(start)
        item.expected_completion_date = date.fromisoformat(expected) if expected else None
        if not relationship.progress:
            db.session.add(LearningProgress(relationship=relationship, learner_id=relationship.learner_id, mentor_id=relationship.mentor_id, skill_id=relationship.skill_id))
        notify(relationship.learner_id, "learning_plan", "Learning plan updated", f"{g.current_user.full_name} updated your learning plan.", "relationship", relationship.id)
        db.session.commit()
        flash("Learning plan saved.", "success")
        return redirect(url_for("learning.progress", relationship_id=relationship.id))
    return render_template("learning/plan.html", relationship=relationship, plan=item)


@learning_bp.route("/mentor/learning/<int:relationship_id>/progress", methods=["GET", "POST"])
@role_required("Mentor")
def mentor_progress(relationship_id):
    relationship = owned_relationship(relationship_id, "Mentor")
    progress = relationship.progress or LearningProgress(relationship=relationship, learner_id=relationship.learner_id, mentor_id=relationship.mentor_id, skill_id=relationship.skill_id)
    if request.method == "POST":
        percentage = request.form.get("percentage", type=int)
        if percentage not in ALLOWED_PROGRESS:
            flash("Progress must be 0, 25, 50, 75, or 100 percent.", "danger")
        else:
            if not progress.id:
                db.session.add(progress)
            progress.percentage = percentage
            progress.completed_topics = request.form.get("completed_topics", "").strip()
            progress.current_topic = request.form.get("current_topic", "").strip()
            progress.remaining_topics = request.form.get("remaining_topics", "").strip()
            progress.mentor_notes = request.form.get("mentor_notes", "").strip()
            progress.completion_status = "Completed" if percentage == 100 else "In Progress"
            if percentage == 100:
                relationship.status = "Completed"
                notify(relationship.learner_id, "learning_completed", "Learning completed", f"Your {relationship.skill.name} learning relationship is complete.", "relationship", relationship.id)
            notify(relationship.learner_id, "progress_updated", "Progress updated", f"{g.current_user.full_name} updated your learning progress.", "relationship", relationship.id)
            db.session.commit()
            flash("Learning progress updated.", "success")
            return redirect(url_for("learning.mentor_progress", relationship_id=relationship.id))
    review = Review.query.filter_by(relationship_id=relationship.id).first()
    recent_activities = Notification.query.filter_by(related_type="relationship", related_id=relationship.id).order_by(Notification.created_at.desc()).limit(6).all()
    return render_template("learning/progress.html", relationship=relationship, progress=progress, review=review, mentor_mode=True, recent_activities=recent_activities)


@learning_bp.get("/learning/<int:relationship_id>/progress")
@role_required("Learner", "Mentor")
def progress(relationship_id):
    relationship = LearningRelationship.query.filter(LearningRelationship.id == relationship_id, LearningRelationship.status.in_(["Active", "Completed"])).first_or_404()
    if g.current_user.id not in {relationship.learner_id, relationship.mentor_id}:
        abort(403)
    review = Review.query.filter_by(relationship_id=relationship.id).first()
    recent_activities = Notification.query.filter_by(related_type="relationship", related_id=relationship.id).order_by(Notification.created_at.desc()).limit(6).all()
    return render_template("learning/progress.html", relationship=relationship, progress=relationship.progress, review=review, mentor_mode=False, recent_activities=recent_activities)
