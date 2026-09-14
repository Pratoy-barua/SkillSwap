"""Learning requests, active relationships, private chat, and notifications."""

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for
from sqlalchemy import or_

from decorators.auth import authenticated_role, role_required
from extensions import db
from models.auth import MentorSkill, Skill, User
from models.connection import Conversation, LearningRelationship, LearningRequest, Message, Notification
from services.notifications import notify


connection_bp = Blueprint("connections", __name__)


def approved_user(user):
    return user and user.account_status == "Approved"


def active_relationship_for(learner_id, mentor_id, skill_id):
    return LearningRelationship.query.filter_by(learner_id=learner_id, mentor_id=mentor_id, skill_id=skill_id, status="Active").first()


@connection_bp.post("/learning-requests/create/<int:mentor_id>")
@role_required("Learner")
def create_request(mentor_id):
    mentor = User.query.get_or_404(mentor_id)
    if mentor.role.name != "Mentor" or not approved_user(mentor) or not mentor.mentor_profile:
        abort(404)
    skill_id = request.form.get("skill_id", type=int)
    skill_link = MentorSkill.query.filter_by(mentor_profile_id=mentor.mentor_profile.id, skill_id=skill_id).join(MentorSkill.skill).filter(Skill.is_active.is_(True)).first()
    if not skill_link:
        abort(400, description="That skill is not available from this mentor.")
    if active_relationship_for(g.current_user.id, mentor.id, skill_id):
        flash("You already have an active learning relationship for this skill.", "info")
        return redirect(url_for("discovery.mentor_profile", user_id=mentor.id))
    duplicate = LearningRequest.query.filter(
        LearningRequest.learner_id == g.current_user.id,
        LearningRequest.mentor_id == mentor.id,
        LearningRequest.skill_id == skill_id,
        LearningRequest.status.in_(["Pending", "Accepted"]),
    ).first()
    if duplicate:
        flash("You already have an active request for this skill.", "info")
        return redirect(url_for("discovery.mentor_profile", user_id=mentor.id))
    item = LearningRequest(learner_id=g.current_user.id, mentor_id=mentor.id, skill_id=skill_id, message=request.form.get("message", "").strip()[:2000], status="Pending")
    db.session.add(item)
    db.session.flush()
    notify(mentor.id, "learning_request", "New learning request", f"{g.current_user.full_name} requested {skill_link.skill.name}.", "learning_request", item.id)
    db.session.commit()
    flash("Your learning request was sent.", "success")
    return redirect(url_for("connections.learner_requests"))


@connection_bp.get("/learner/requests")
@role_required("Learner")
def learner_requests():
    items = LearningRequest.query.filter_by(learner_id=g.current_user.id).order_by(LearningRequest.created_at.desc()).all()
    return render_template("connections/learner_requests.html", requests=items)


@connection_bp.post("/learner/requests/<int:request_id>/cancel")
@role_required("Learner")
def cancel_request(request_id):
    item = LearningRequest.query.filter_by(id=request_id, learner_id=g.current_user.id).first_or_404()
    if item.status == "Pending":
        item.status = "Cancelled"
        notify(item.mentor_id, "request_cancelled", "Learning request cancelled", f"{g.current_user.full_name} cancelled a request.", "learning_request", item.id)
        db.session.commit()
        flash("Request cancelled.", "success")
    return redirect(url_for("connections.learner_requests"))


@connection_bp.get("/mentor/requests")
@role_required("Mentor")
def mentor_requests():
    items = LearningRequest.query.filter_by(mentor_id=g.current_user.id).order_by(LearningRequest.created_at.desc()).all()
    active_rels = LearningRelationship.query.filter_by(mentor_id=g.current_user.id, status="Active").all()
    conversations_by_learner = {}
    for rel in active_rels:
        if not rel.conversation:
            rel.conversation = Conversation(relationship=rel)
            db.session.commit()
        conversations_by_learner[rel.learner_id] = rel.conversation.id
    return render_template("connections/mentor_requests.html", requests=items, conversations_by_learner=conversations_by_learner)


@connection_bp.post("/mentor/requests/<int:request_id>/<action>")
@role_required("Mentor")
def mentor_request_action(request_id, action):
    item = LearningRequest.query.filter_by(id=request_id, mentor_id=g.current_user.id).first_or_404()
    if item.status != "Pending" or action not in {"accept", "reject"}:
        abort(400)
    if action == "reject":
        item.status = "Rejected"
        notify(item.learner_id, "request_rejected", "Learning request rejected", f"{g.current_user.full_name} rejected your request.", "learning_request", item.id)
    else:
        item.status = "Accepted"
        relationship = LearningRelationship.query.filter_by(learner_id=item.learner_id, mentor_id=item.mentor_id, skill_id=item.skill_id, status="Active").first()
        if not relationship:
            relationship = LearningRelationship(learner_id=item.learner_id, mentor_id=item.mentor_id, skill_id=item.skill_id, request=item, status="Active")
            db.session.add(relationship)
            db.session.flush()
            db.session.add(Conversation(relationship=relationship))
            notify(item.learner_id, "relationship_created", "Learning request accepted", f"{g.current_user.full_name} accepted your request.", "relationship", relationship.id)
        else:
            item.relationship = relationship
    db.session.commit()
    flash(f"Request {item.status.lower()}.", "success")
    return redirect(url_for("connections.mentor_requests"))


@connection_bp.get("/learner/mentors")
@role_required("Learner")
def learner_mentors():
    relationships = LearningRelationship.query.filter_by(learner_id=g.current_user.id, status="Active").order_by(LearningRelationship.started_at.desc()).all()
    return render_template("connections/learner_mentors.html", relationships=relationships)


@connection_bp.get("/mentor/learners")
@role_required("Mentor")
def mentor_learners():
    relationships = LearningRelationship.query.filter_by(mentor_id=g.current_user.id, status="Active").order_by(LearningRelationship.started_at.desc()).all()
    return render_template("connections/mentor_learners.html", relationships=relationships)


def authorized_conversation(conversation_id):
    conversation = Conversation.query.get_or_404(conversation_id)
    relationship = conversation.relationship
    if relationship.status != "Active" or g.current_user.id not in {relationship.learner_id, relationship.mentor_id}:
        abort(403)
    return conversation


@connection_bp.get("/chat")
@role_required("Learner", "Mentor")
def chat_list():
    relationships = LearningRelationship.query.filter(or_(LearningRelationship.learner_id == g.current_user.id, LearningRelationship.mentor_id == g.current_user.id), LearningRelationship.status == "Active").all()
    return render_template("connections/chat_list.html", relationships=relationships)


@connection_bp.route("/chat/<int:conversation_id>", methods=["GET", "POST"])
@role_required("Learner", "Mentor")
def chat(conversation_id):
    conversation = authorized_conversation(conversation_id)
    if request.method == "POST":
        body = request.form.get("body", "").strip()[:4000]
        if not body:
            flash("Message cannot be empty.", "danger")
        else:
            recipient_id = conversation.relationship.mentor_id if g.current_user.id == conversation.relationship.learner_id else conversation.relationship.learner_id
            db.session.add(Message(conversation=conversation, sender_id=g.current_user.id, body=body))
            notify(recipient_id, "chat_message", "New chat message", f"{g.current_user.full_name} sent you a message.", "conversation", conversation.id)
            db.session.commit()
            return redirect(url_for("connections.chat", conversation_id=conversation.id))
    for message in conversation.messages:
        if message.sender_id != g.current_user.id:
            message.is_read = True
    db.session.commit()
    return render_template("connections/chat.html", conversation=conversation)


@connection_bp.get("/chat/<int:conversation_id>/messages")
@role_required("Learner", "Mentor")
def chat_messages(conversation_id):
    conversation = authorized_conversation(conversation_id)
    for message in conversation.messages:
        if message.sender_id != g.current_user.id:
            message.is_read = True
    db.session.commit()
    return jsonify({"messages": [{"id": item.id, "body": item.body, "sender": item.sender.full_name, "mine": item.sender_id == g.current_user.id, "created_at": item.created_at.isoformat()} for item in conversation.messages]})


@connection_bp.get("/chat/with/<int:user_id>")
@role_required("Learner", "Mentor")
def chat_with_user(user_id):
    target = User.query.get_or_404(user_id)
    if g.current_user.role.name == "Mentor":
        relationship = LearningRelationship.query.filter_by(
            mentor_id=g.current_user.id, learner_id=target.id, status="Active"
        ).first()
        if not relationship:
            pending = LearningRequest.query.filter_by(
                mentor_id=g.current_user.id, learner_id=target.id, status="Pending"
            ).first()
            if pending:
                flash("Please accept the learner's request to start chatting.", "info")
                return redirect(url_for("learner.view_profile", user_id=target.id))
            abort(403)
    else:  # Learner
        relationship = LearningRelationship.query.filter_by(
            learner_id=g.current_user.id, mentor_id=target.id, status="Active"
        ).first()
        if not relationship:
            pending = LearningRequest.query.filter_by(
                learner_id=g.current_user.id, mentor_id=target.id, status="Pending"
            ).first()
            if pending:
                flash("Your learning request is pending mentor approval. Once accepted, you can message this mentor.", "info")
            else:
                flash("Send a learning request to start learning and chatting with this mentor.", "info")
            return redirect(url_for("discovery.mentor_profile", user_id=target.id))

    if not relationship.conversation:
        relationship.conversation = Conversation(relationship=relationship)
        db.session.commit()

    return redirect(url_for("connections.chat", conversation_id=relationship.conversation.id))


@connection_bp.get("/notifications")
@authenticated_role("Learner", "Mentor", "Admin")
def notifications():
    items = Notification.query.filter_by(user_id=g.current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template("connections/notifications.html", notifications=items)


@connection_bp.post("/notifications/<int:notification_id>/read")
@authenticated_role("Learner", "Mentor", "Admin")
def mark_notification_read(notification_id):
    item = Notification.query.filter_by(id=notification_id, user_id=g.current_user.id).first_or_404()
    item.is_read = True
    db.session.commit()
    return redirect(url_for("connections.notifications"))


@connection_bp.post("/notifications/read-all")
@authenticated_role("Learner", "Mentor", "Admin")
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=g.current_user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    return redirect(url_for("connections.notifications"))


@connection_bp.get("/notifications/<int:notification_id>/open")
@authenticated_role("Learner", "Mentor", "Admin")
def open_notification(notification_id):
    item = Notification.query.filter_by(id=notification_id, user_id=g.current_user.id).first_or_404()
    item.is_read = True
    db.session.commit()

    # If it is a chat notification, directly open the conversation
    if item.related_type == "conversation" and item.related_id:
        conversation = Conversation.query.get(item.related_id)
        if conversation and conversation.relationship.status == "Active":
            if g.current_user.id in {conversation.relationship.learner_id, conversation.relationship.mentor_id}:
                return redirect(url_for("connections.chat", conversation_id=conversation.id))

    if item.notification_type == "chat_message":
        if item.related_type == "conversation" and item.related_id:
            return redirect(url_for("connections.chat", conversation_id=item.related_id))

    # If it is a relationship notification (e.g. relationship_created)
    if item.related_type == "relationship" and item.related_id:
        relationship = LearningRelationship.query.get(item.related_id)
        if relationship and relationship.status == "Active" and relationship.conversation:
            if g.current_user.id in {relationship.learner_id, relationship.mentor_id}:
                return redirect(url_for("connections.chat", conversation_id=relationship.conversation.id))
        if g.current_user.role.name == "Mentor":
            return redirect(url_for("connections.mentor_learners"))
        return redirect(url_for("connections.learner_mentors"))

    # If it is a learning request notification
    if item.related_type == "learning_request" or item.notification_type.startswith("request_"):
        if g.current_user.role.name == "Mentor":
            return redirect(url_for("connections.mentor_requests"))
        return redirect(url_for("connections.learner_requests"))

    return redirect(url_for("connections.notifications"))
