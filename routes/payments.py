"""Server-calculated demo payments and basic subscriptions."""

from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from decorators.auth import role_required
from extensions import db
from models.connection import LearningRelationship
from models.learning import LearningPlan, Payment, PlatformSetting, Subscription
from services.notifications import notify
from services.payments import DemoPaymentProvider, split_amount
from services.revenue import record_revenue


payment_bp = Blueprint("payments", __name__)


@payment_bp.route("/payments/checkout/<int:relationship_id>", methods=["GET", "POST"])
@role_required("Learner")
def checkout(relationship_id):
    relationship = LearningRelationship.query.filter_by(id=relationship_id, learner_id=g.current_user.id, status="Active").first_or_404()
    plan = relationship.plan
    if not plan:
        flash("Your mentor has not published a learning plan yet.", "warning")
        return redirect(url_for("connections.learner_mentors"))
    if request.method == "POST":
        payment_type = request.form.get("payment_type", "Course-based")
        if payment_type not in {"Daily", "Weekly", "Monthly", "Course-based"}:
            abort(400)
        outcome = request.form.get("demo_outcome", "success")
        duplicate = Payment.query.filter_by(learner_id=g.current_user.id, relationship_id=relationship.id, payment_type=payment_type, status="Successful").first()
        if duplicate and outcome == "success":
            flash("This payment type has already been completed for this learning plan.", "info")
            return redirect(url_for("payments.history"))
        amount, commission, earning = split_amount(plan.pricing, db.session)
        result = DemoPaymentProvider().charge(amount, outcome if outcome in {"success", "failure"} else "failure")
        payment = Payment(learner_id=g.current_user.id, mentor_id=relationship.mentor_id, relationship_id=relationship.id, amount=amount, payment_type=payment_type, reference_id=result["reference_id"], status=result["status"], payment_date=date.today() if result["status"] == "Successful" else None, platform_commission=commission, mentor_earning=earning)
        db.session.add(payment)
        db.session.flush()
        if result["status"] == "Successful":
            record_revenue("Mentor Payment", payment.id, payment.amount, payment.platform_commission, payment.mentor_earning)
        notify(g.current_user.id, "payment_successful" if result["status"] == "Successful" else "payment_failed", f"Demo payment {result['status'].lower()}", f"Your Demo Payment reference is {payment.reference_id}.", "payment", payment.id if payment.id else None)
        notify(relationship.mentor_id, "payment_successful" if result["status"] == "Successful" else "payment_failed", f"Demo payment {result['status'].lower()}", f"A Demo Payment for {relationship.skill.name} is {result['status'].lower()}.", "relationship", relationship.id)
        db.session.commit()
        return redirect(url_for("payments.result", payment_id=payment.id))
    return render_template("payments/checkout.html", relationship=relationship, plan=plan)


@payment_bp.get("/payments/result/<int:payment_id>")
@role_required("Learner")
def result(payment_id):
    payment = Payment.query.filter_by(id=payment_id, learner_id=g.current_user.id).first_or_404()
    return render_template("payments/result.html", payment=payment)


@payment_bp.get("/learner/payments")
@role_required("Learner")
def history():
    payments = Payment.query.filter_by(learner_id=g.current_user.id).order_by(Payment.created_at.desc()).all()
    return render_template("payments/history.html", payments=payments, mentor_mode=False)


@payment_bp.get("/mentor/earnings")
@role_required("Mentor")
def earnings():
    payments = Payment.query.filter_by(mentor_id=g.current_user.id).order_by(Payment.created_at.desc()).all()
    return render_template("payments/history.html", payments=payments, mentor_mode=True)


@payment_bp.route("/subscription", methods=["GET", "POST"])
@role_required("Learner", "Mentor")
def subscription():
    current = Subscription.query.filter_by(user_id=g.current_user.id, status="Active").order_by(Subscription.expiry_date.desc()).first()
    if current and current.expiry_date and current.expiry_date < date.today():
        current.status = "Expired"
        db.session.commit()
        current = None
    if request.method == "POST":
        if request.form.get("plan") != "Premium":
            abort(400)
        price_setting = PlatformSetting.query.filter_by(key="premium_subscription_price").first()
        if not price_setting:
            price_setting = PlatformSetting(key="premium_subscription_price", value="100")
            db.session.add(price_setting)
            db.session.flush()
        amount = Decimal(price_setting.value)
        outcome = request.form.get("demo_outcome", "success")
        result = DemoPaymentProvider().charge(amount, outcome if outcome in {"success", "failure"} else "failure")
        status = result["status"]
        subscription_item = Subscription(user_id=g.current_user.id, plan="Premium", amount=amount, start_date=date.today() if status == "Successful" else None, expiry_date=date.today() + timedelta(days=30) if status == "Successful" else None, status="Active" if status == "Successful" else "Pending", payment_reference=result["reference_id"])
        db.session.add(subscription_item)
        db.session.flush()
        if status == "Successful":
            record_revenue("Subscription", subscription_item.id, amount, amount, 0)
        notify(g.current_user.id, "subscription_activated" if status == "Successful" else "payment_failed", "Subscription update", f"Your Demo Subscription is {status.lower()}.", "subscription", subscription_item.id)
        db.session.commit()
        flash(f"Demo subscription is {status.lower()}.", "success" if status == "Successful" else "warning")
        return redirect(url_for("payments.subscription"))
    return render_template("payments/subscription.html", subscription=current)
