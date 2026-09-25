"""Server-calculated demo payments and basic subscriptions."""

from datetime import date, timedelta
from decimal import Decimal

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from decorators.auth import role_required
from extensions import db
from models.auth import Role, User
from models.connection import LearningRelationship
from models.learning import LearningPlan, MentorProfileAccess, Payment, PlatformSetting, Subscription
from services.notifications import notify
from services.payments import DemoPaymentProvider, get_mentor_unlock_fee, split_amount
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
        notify(g.current_user.id, "payment_successful" if result["status"] == "Successful" else "payment_failed", "Payment successful" if result["status"] == "Successful" else "Payment failed", f"Your payment of ৳{payment.amount} for {relationship.skill.name} was {result['status'].lower()}.", "payment", payment.id if payment.id else None)
        notify(relationship.mentor_id, "payment_successful" if result["status"] == "Successful" else "payment_failed", "Payment received" if result["status"] == "Successful" else "Payment failed", f"A payment of ৳{payment.amount} for {relationship.skill.name} was {result['status'].lower()}.", "relationship", relationship.id)
        db.session.commit()
        return redirect(url_for("payments.result", payment_id=payment.id))
    amount, commission, earning = split_amount(plan.pricing, db.session)
    return render_template("payments/checkout.html", relationship=relationship, plan=plan, amount=amount, commission=commission, earning=earning)


@payment_bp.get("/payments/result/<int:payment_id>")
@role_required("Learner")
def result(payment_id):
    payment = Payment.query.filter_by(id=payment_id, learner_id=g.current_user.id).first_or_404()
    return render_template("payments/result.html", payment=payment)


@payment_bp.get("/payments/invoice/<int:payment_id>")
@role_required("Learner", "Mentor", "Admin")
def invoice(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if g.current_user.role.name != "Admin" and g.current_user.id not in {payment.learner_id, payment.mentor_id}:
        abort(403)
    return render_template("payments/invoice.html", payment=payment)


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


@payment_bp.route("/payments/mentor/<int:mentor_id>/unlock-details", methods=["GET", "POST"])
@payment_bp.route("/mentor/<int:mentor_id>/unlock-details", methods=["GET", "POST"])
@role_required("Learner")
def unlock_mentor_details(mentor_id):
    mentor = (
        User.query.join(User.role)
        .filter(User.id == mentor_id, Role.name == "Mentor", User.account_status == "Approved")
        .first_or_404()
    )

    # Reject unlock attempt if mentor has no professional contact details
    raw_profile = mentor.mentor_profile
    has_any_contact = bool(
        raw_profile and (
            (raw_profile.linkedin_url and raw_profile.linkedin_url.strip())
            or (raw_profile.github_url and raw_profile.github_url.strip())
            or (raw_profile.website_url and raw_profile.website_url.strip())
        )
    )
    if not has_any_contact:
        flash(f"{mentor.full_name} does not have any professional contact details to unlock.", "warning")
        return redirect(url_for("discovery.mentor_profile", user_id=mentor.id))

    # Check if already unlocked
    existing = MentorProfileAccess.query.filter_by(
        learner_id=g.current_user.id, mentor_id=mentor.id
    ).first()
    if existing:
        flash(f"You have already unlocked {mentor.full_name}'s contact details.", "info")
        return redirect(url_for("discovery.mentor_profile", user_id=mentor.id))

    fee = get_mentor_unlock_fee(db.session)

    if request.method == "POST":
        outcome = request.form.get("demo_outcome", "success")
        result = DemoPaymentProvider().charge(fee, outcome if outcome in {"success", "failure"} else "failure")

        payment = Payment(
            learner_id=g.current_user.id,
            mentor_id=mentor.id,
            relationship_id=None,
            amount=fee,
            payment_type="Profile Unlock",
            reference_id=result["reference_id"],
            status=result["status"],
            payment_date=date.today() if result["status"] == "Successful" else None,
            platform_commission=fee,
            mentor_earning=0,
        )
        db.session.add(payment)
        db.session.flush()

        if result["status"] == "Successful":
            access = MentorProfileAccess(
                learner_id=g.current_user.id,
                mentor_id=mentor.id,
                payment_id=payment.id,
            )
            db.session.add(access)
            record_revenue("Profile Unlock", payment.id, payment.amount, payment.platform_commission, 0)
            notify(
                g.current_user.id,
                "profile_unlocked",
                "Profile Details Unlocked",
                f"You have unlocked {mentor.full_name}'s professional contact details.",
                "payment",
                payment.id,
            )
            db.session.commit()
            flash(f"Successfully unlocked {mentor.full_name}'s contact details!", "success")
            return redirect(url_for("discovery.mentor_profile", user_id=mentor.id))
        else:
            notify(
                g.current_user.id,
                "payment_failed",
                "Payment Failed",
                f"Your payment of ৳{payment.amount} to unlock {mentor.full_name}'s details was unsuccessful.",
                "payment",
                payment.id,
            )
            db.session.commit()
            flash("Demo payment was marked as failed. Please try again.", "danger")
            return render_template("payments/unlock_checkout.html", mentor=mentor, fee=fee)

    return render_template("payments/unlock_checkout.html", mentor=mentor, fee=fee)

