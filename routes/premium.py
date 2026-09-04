"""Configurable premium plans and demo activation flow."""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from decorators.auth import role_required
from extensions import db
from models.learning import Subscription
from models.reviews import PremiumPlan
from services.notifications import notify
from services.payments import DemoPaymentProvider
from services.revenue import record_revenue
from services.premium import active_subscription

premium_bp = Blueprint("premium", __name__)


@premium_bp.get("/premium/plans")
@role_required("Learner", "Mentor")
def plans():
    available = PremiumPlan.query.filter_by(is_active=True).order_by(PremiumPlan.price).all()
    if not available:
        available = [PremiumPlan(name="Plus", price=Decimal("100.00"), duration_days=30, description="A configurable starter premium plan.", features="Advanced search and priority visibility")]
        db.session.add(available[0])
        db.session.commit()
    return render_template("premium/plans.html", plans=available, subscription=active_subscription(g.current_user.id))


@premium_bp.post("/premium/activate/<int:plan_id>")
@role_required("Learner", "Mentor")
def activate(plan_id):
    plan = PremiumPlan.query.filter_by(id=plan_id, is_active=True).first_or_404()
    outcome = request.form.get("demo_outcome", "success")
    result = DemoPaymentProvider().charge(plan.price, outcome if outcome in {"success", "failure"} else "failure")
    item = Subscription(user_id=g.current_user.id, plan=plan.name, premium_plan_id=plan.id, amount=plan.price, start_date=date.today() if result["status"] == "Successful" else None, expiry_date=date.today() + timedelta(days=plan.duration_days) if result["status"] == "Successful" else None, status="Active" if result["status"] == "Successful" else "Pending", payment_reference=result["reference_id"])
    db.session.add(item)
    db.session.flush()
    if result["status"] == "Successful":
        record_revenue("Premium", item.id, item.amount, item.amount, 0)
    notify(g.current_user.id, "subscription_activated" if result["status"] == "Successful" else "payment_failed", "Premium plan update", f"Your Demo Premium payment is {result['status'].lower()}.", "subscription", item.id)
    db.session.commit()
    flash(f"Demo Premium payment is {result['status'].lower()}.", "success" if result["status"] == "Successful" else "warning")
    return redirect(url_for("premium.plans"))


@premium_bp.route("/admin/premium/plans", methods=["GET", "POST"])
@role_required("Admin")
def admin_plans():
    if request.method == "POST":
        try:
            price = Decimal(request.form.get("price", "0"))
            days = int(request.form.get("duration_days", "30"))
        except (InvalidOperation, ValueError):
            flash("Price and duration must be valid.", "danger")
            return redirect(url_for("premium.admin_plans"))
        name = request.form.get("name", "").strip()[:80]
        if not name or price < 0 or days < 1 or PremiumPlan.query.filter_by(name=name).first():
            flash("Use a unique name and valid plan values.", "danger")
        else:
            db.session.add(PremiumPlan(name=name, price=price, duration_days=days, description=request.form.get("description", "").strip()[:2000], features=request.form.get("features", "").strip()[:4000]))
            db.session.commit()
            flash("Premium plan created.", "success")
    return render_template("admin/premium_plans.html", plans=PremiumPlan.query.order_by(PremiumPlan.created_at.desc()).all())


@premium_bp.post("/admin/premium/plans/<int:plan_id>/toggle")
@role_required("Admin")
def toggle_plan(plan_id):
    plan = PremiumPlan.query.get_or_404(plan_id)
    plan.is_active = not plan.is_active
    db.session.commit()
    return redirect(url_for("premium.admin_plans"))
