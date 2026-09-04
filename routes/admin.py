"""Admin verification and account-status management."""

from pathlib import Path

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, send_file, url_for, request
from sqlalchemy import func, or_

from decorators.auth import role_required
from extensions import db
from models.auth import Role, Skill, User, VerificationDocument
from models.learning import LearningProgress, Payment, Subscription
from models.connection import LearningRelationship
from models.store import Order, ProductCategory
from models.reviews import PremiumPlan, RevenueRecord, Review


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/dashboard")
@role_required("Admin")
def dashboard():
    pending_learners = User.query.join(User.role).filter(Role.name == "Learner", User.account_status == "Pending").order_by(User.created_at).all()
    pending_mentors = User.query.join(User.role).filter(Role.name == "Mentor", User.account_status == "Pending").order_by(User.created_at).all()
    counts = {
        "learners": User.query.join(User.role).filter(Role.name == "Learner").count(),
        "mentors": User.query.join(User.role).filter(Role.name == "Mentor").count(),
        "pending_users": User.query.filter_by(account_status="Pending").count(),
        "approved_users": User.query.filter_by(account_status="Approved").count(),
        "active_users": User.query.filter_by(account_status="Approved").count(),
        "suspended_users": User.query.filter_by(account_status="Suspended").count(),
        "skills": Skill.query.count(), "active_skills": Skill.query.filter_by(is_active=True).count(),
        "relationships": LearningRelationship.query.filter_by(status="Active").count(),
        "payments": Payment.query.count(), "successful_payments": Payment.query.filter_by(status="Successful").count(),
        "orders": Order.query.count(), "reviews": Review.query.count(),
        "revenue": sum((item.net_platform_revenue for item in RevenueRecord.query.filter_by(status="Successful").all()), 0),
        "premium_subscribers": Subscription.query.filter_by(status="Active").count(),
    }
    return render_template("admin/dashboard.html", pending_learners=pending_learners, pending_mentors=pending_mentors, counts=counts)


@admin_bp.get("/users")
@role_required("Admin")
def users():
    search = request.args.get("q", "").strip()
    role = request.args.get("role", "")
    status = request.args.get("status", "")
    query = User.query.join(User.role)
    if search:
        query = query.filter(or_(User.full_name.ilike(f"%{search}%"), User.email.ilike(f"%{search}%")))
    if role in {"Learner", "Mentor", "Admin"}:
        query = query.filter(Role.name == role)
    if status in {"Pending", "Approved", "Rejected", "Suspended"}:
        query = query.filter(User.account_status == status)
    return render_template("admin/users.html", users=query.order_by(User.created_at.desc()).all(), filters=request.args)


@admin_bp.get("/users/<int:user_id>")
@role_required("Admin")
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    if user.role.name == "Admin":
        abort(403)
    return render_template("admin/user_detail.html", user=user)


@admin_bp.post("/users/<int:user_id>/<action>")
@role_required("Admin")
def user_action(user_id, action):
    user = User.query.get_or_404(user_id)
    if user.role.name == "Admin":
        abort(403)
    transitions = {"approve": "Approved", "reject": "Rejected", "suspend": "Suspended", "reactivate": "Approved"}
    if action not in transitions:
        abort(404)
    user.account_status = transitions[action]
    db.session.commit()
    flash(f"{user.full_name} is now {user.account_status}.", "success")
    return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.get("/documents/<int:document_id>")
@role_required("Admin")
def document(document_id):
    item = VerificationDocument.query.get_or_404(document_id)
    base = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"]).resolve()
    path = (base / item.stored_name).resolve()
    if path.parent != base:
        abort(404)
    if not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=item.original_name)


@admin_bp.route("/skills", methods=["GET", "POST"])
@role_required("Admin")
def skills():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Skill name is required.", "danger")
        elif Skill.query.filter(func.lower(Skill.name) == name.lower()).first():
            flash("That skill already exists.", "warning")
        else:
            db.session.add(Skill(name=name, is_active=True))
            db.session.commit()
            flash("Skill added.", "success")
            return redirect(url_for("admin.skills"))
    return render_template("admin/skills.html", skills=Skill.query.order_by(Skill.name).all())


@admin_bp.post("/skills/<int:skill_id>/toggle")
@role_required("Admin")
def toggle_skill(skill_id):
    skill = Skill.query.get_or_404(skill_id)
    skill.is_active = not skill.is_active
    db.session.commit()
    flash(f"{skill.name} is now {'active' if skill.is_active else 'inactive'}.", "success")
    return redirect(url_for("admin.skills"))


@admin_bp.get("/payments")
@role_required("Admin")
def payments():
    records = Payment.query.order_by(Payment.created_at.desc()).all()
    successful = [item for item in records if item.status == "Successful"]
    return render_template("admin/payments.html", payments=records, total_transactions=len(records), successful_count=len(successful), gross=sum((item.amount for item in successful), 0), commission=sum((item.platform_commission for item in successful), 0), mentor_earnings=sum((item.mentor_earning for item in successful), 0), subscription_revenue=sum((item.amount for item in Subscription.query.filter_by(status="Active").all()), 0))


@admin_bp.get("/revenue")
@role_required("Admin")
def revenue():
    records = RevenueRecord.query.filter_by(status="Successful").order_by(RevenueRecord.created_at.desc()).all()
    by_source = {}
    for record in records:
        row = by_source.setdefault(record.source_type, {"gross": 0, "net": 0, "count": 0})
        row["gross"] += record.gross_amount
        row["net"] += record.net_platform_revenue
        row["count"] += 1
    return render_template("admin/revenue.html", records=records, by_source=by_source, total=sum((item.net_platform_revenue for item in records), 0))


@admin_bp.route("/store/categories", methods=["GET", "POST"])
@role_required("Admin")
def store_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name or ProductCategory.query.filter(func.lower(ProductCategory.name) == name.lower()).first():
            flash("A unique category name is required.", "danger")
        else:
            db.session.add(ProductCategory(name=name, is_active=True))
            db.session.commit()
            flash("Category created.", "success")
            return redirect(url_for("admin.store_categories"))
    return render_template("admin/store_categories.html", categories=ProductCategory.query.order_by(ProductCategory.name).all())


@admin_bp.post("/store/categories/<int:category_id>/toggle")
@role_required("Admin")
def toggle_store_category(category_id):
    category = ProductCategory.query.get_or_404(category_id)
    category.is_active = not category.is_active
    db.session.commit()
    return redirect(url_for("admin.store_categories"))


@admin_bp.get("/store/orders")
@role_required("Admin")
def store_orders():
    return render_template("admin/store_orders.html", orders=Order.query.order_by(Order.created_at.desc()).all())


@admin_bp.post("/store/orders/<int:order_id>/status")
@role_required("Admin")
def update_store_order(order_id):
    order = Order.query.get_or_404(order_id)
    status = request.form.get("status")
    if status not in {"Pending", "Confirmed", "Processing", "Shipped", "Delivered", "Cancelled"}:
        abort(400)
    order.order_status = status
    db.session.commit()
    flash("Order status updated.", "success")
    return redirect(url_for("admin.store_orders"))
