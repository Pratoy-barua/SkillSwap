"""Admin verification and account-status management."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, send_file, url_for, request
from sqlalchemy import func, or_

from decorators.auth import role_required
from extensions import db
from models.auth import Role, Skill, User, VerificationDocument
from models.learning import LearningProgress, Payment, Subscription
from models.connection import LearningRelationship
from models.store import CartItem, Order, OrderItem, Product, ProductCategory
from models.reviews import PremiumPlan, RevenueRecord, Review
from services.notifications import notify
from services.uploads import save_upload


admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def get_business_analytics(months_limit=6):
    """
    Aggregates real business metrics from the existing database:
    1. Net Revenue: RevenueRecord with status == 'Successful', summing net_platform_revenue.
    2. Store Orders: Order, counting actual store orders.
    3. Successful Payments: Payment with status == 'Successful', counting completed transactions.

    Aggregated with GROUP BY using func.extract('year', ...) and func.extract('month', ...).
    Returns only real historical data months (up to months_limit). Never invents missing months/data.
    """
    rev_q = (
        db.session.query(
            func.extract("year", RevenueRecord.created_at).label("yr"),
            func.extract("month", RevenueRecord.created_at).label("mo"),
            func.sum(RevenueRecord.net_platform_revenue).label("net_rev"),
        )
        .filter(RevenueRecord.status == "Successful")
        .group_by("yr", "mo")
        .all()
    )
    rev_map = {(int(r.yr), int(r.mo)): float(r.net_rev or 0) for r in rev_q}

    ord_q = (
        db.session.query(
            func.extract("year", Order.created_at).label("yr"),
            func.extract("month", Order.created_at).label("mo"),
            func.count(Order.id).label("cnt"),
        )
        .group_by("yr", "mo")
        .all()
    )
    ord_map = {(int(r.yr), int(r.mo)): int(r.cnt or 0) for r in ord_q}

    pay_q = (
        db.session.query(
            func.extract("year", Payment.created_at).label("yr"),
            func.extract("month", Payment.created_at).label("mo"),
            func.count(Payment.id).label("cnt"),
        )
        .filter(Payment.status == "Successful")
        .group_by("yr", "mo")
        .all()
    )
    pay_map = {(int(r.yr), int(r.mo)): int(r.cnt or 0) for r in pay_q}

    all_months = sorted(set(rev_map.keys()) | set(ord_map.keys()) | set(pay_map.keys()))

    if not all_months:
        return {
            "has_data": False,
            "range": months_limit,
            "months": [],
            "revenue": [],
            "orders": [],
            "payments": [],
            "total_revenue": 0.0,
            "total_orders": 0,
            "total_payments": 0,
        }

    selected = all_months[-months_limit:]
    labels = [datetime(y, m, 1).strftime("%b %Y") for y, m in selected]
    revs = [round(rev_map.get(k, 0.0), 2) for k in selected]
    ords = [ord_map.get(k, 0) for k in selected]
    pays = [pay_map.get(k, 0) for k in selected]

    return {
        "has_data": True,
        "range": months_limit,
        "months": labels,
        "revenue": revs,
        "orders": ords,
        "payments": pays,
        "total_revenue": round(sum(revs), 2),
        "total_orders": sum(ords),
        "total_payments": sum(pays),
    }


@admin_bp.get("/api/business-analytics")
@role_required("Admin")
def business_analytics_api():
    try:
        months_limit = int(request.args.get("range", 6))
        if months_limit not in (6, 12):
            months_limit = 6
    except (ValueError, TypeError):
        months_limit = 6

    return jsonify(get_business_analytics(months_limit=months_limit))


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
        "products": Product.query.count(),
    }
    business_data = get_business_analytics(months_limit=6)
    return render_template("admin/dashboard.html", pending_learners=pending_learners, pending_mentors=pending_mentors, counts=counts, business_data=business_data)



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

    if action == "delete":
        return delete_user(user_id)

    transitions = {"approve": "Approved", "reject": "Rejected", "suspend": "Suspended", "reactivate": "Approved"}
    if action not in transitions:
        abort(404)

    if action == "reject":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("A reason for rejection is required.", "danger")
            return redirect(url_for("admin.user_detail", user_id=user.id))

        user.account_status = "Rejected"
        role_label = user.role.name.lower()
        notify(
            user_id=user.id,
            notification_type="application_rejected",
            title="Application Rejected",
            message=f"Your {role_label} application has been rejected by the administrator.\n\nReason:\n{reason}",
            related_type="user",
            related_id=user.id,
        )
        db.session.commit()
        flash(f"{user.full_name}'s application has been rejected.", "success")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    elif action == "suspend":
        reason = request.form.get("reason", "").strip()
        if not reason:
            flash("A reason for suspension is required.", "danger")
            return redirect(url_for("admin.user_detail", user_id=user.id))

        user.account_status = "Suspended"
        notify(
            user_id=user.id,
            notification_type="account_suspended",
            title="Account Suspended",
            message=f"Your SkillSwap account has been suspended by the administrator.\n\nReason:\n{reason}",
            related_type="user",
            related_id=user.id,
        )
        db.session.commit()
        flash(f"{user.full_name}'s account has been suspended.", "success")
        return redirect(url_for("admin.user_detail", user_id=user.id))

    elif action in ("approve", "reactivate"):
        user.account_status = "Approved"
        db.session.commit()
        action_word = "approved" if action == "approve" else "reactivated"
        flash(f"{user.full_name} is now {action_word}.", "success")
        return redirect(url_for("admin.user_detail", user_id=user.id))


@admin_bp.post("/users/<int:user_id>/delete")
@role_required("Admin")
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role.name == "Admin":
        abort(403)

    user_name = user.full_name
    try:
        # Clean up private documents from disk
        for doc in user.documents:
            try:
                base = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"]).resolve()
                doc_path = (base / doc.stored_name).resolve()
                if doc_path.is_file():
                    doc_path.unlink(missing_ok=True)
            except Exception:
                pass

        # Clean up profile photo from disk
        if user.profile_photo:
            try:
                pub_base = Path(current_app.config["PUBLIC_UPLOAD_FOLDER"]).resolve()
                photo_path = (pub_base / user.profile_photo).resolve()
                if photo_path.is_file():
                    photo_path.unlink(missing_ok=True)
            except Exception:
                pass

        db.session.delete(user)
        db.session.commit()
        flash(f"Account for {user_name} has been permanently deleted.", "success")
        return redirect(url_for("admin.users"))
    except Exception:
        db.session.rollback()
        flash("Unable to delete user due to a database constraint.", "danger")
        return redirect(url_for("admin.user_detail", user_id=user_id))


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
    new_status = request.form.get("status")
    allowed_statuses = {"Processing", "Confirmed", "Shipped", "Delivered", "Cancelled"}
    if new_status not in allowed_statuses:
        abort(400, description="Invalid order status.")

    if new_status == order.order_status:
        flash(f"Order #{order.id} is already {new_status}.", "info")
        return redirect(url_for("admin.store_orders"))

    # Valid transitions logic
    valid_transitions = {
        "Pending": {"Processing", "Confirmed", "Cancelled"},
        "Processing": {"Confirmed", "Shipped", "Cancelled"},
        "Confirmed": {"Processing", "Shipped", "Cancelled"},
        "Shipped": {"Delivered", "Cancelled"},
        "Delivered": set(),
        "Cancelled": set(),
    }
    allowed_targets = valid_transitions.get(order.order_status, set())
    if new_status not in allowed_targets:
        flash(f"Cannot transition order #{order.id} from {order.order_status} to {new_status}.", "warning")
        return redirect(url_for("admin.store_orders"))

    order.order_status = new_status

    status_messages = {
        "Confirmed": ("Order Confirmed", f"Order #{order.id} has been confirmed."),
        "Processing": ("Order Processing", f"Order #{order.id} is being processed."),
        "Shipped": ("Order Shipped", f"Order #{order.id} has been shipped."),
        "Delivered": ("Order Delivered", f"Order #{order.id} has been delivered."),
        "Cancelled": ("Order Cancelled", f"Order #{order.id} has been cancelled."),
    }

    if new_status in status_messages:
        title, message = status_messages[new_status]
        notify(
            user_id=order.buyer_id,
            notification_type="order_status",
            title=title,
            message=message,
            related_type="order",
            related_id=order.id,
        )

    db.session.commit()
    flash(f"Order #{order.id} status updated to {new_status}.", "success")
    return redirect(url_for("admin.store_orders"))


@admin_bp.get("/store/products")
@role_required("Admin")
def store_products():
    q = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)
    stock_filter = request.args.get("stock_status", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Product.query

    if q:
        search_pattern = f"%{q}%"
        query = query.filter(or_(Product.name.ilike(search_pattern), Product.description.ilike(search_pattern)))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if stock_filter == "in_stock":
        query = query.filter(Product.stock > 5)
    elif stock_filter == "low_stock":
        query = query.filter(Product.stock > 0, Product.stock <= 5)
    elif stock_filter == "out_of_stock":
        query = query.filter(Product.stock == 0)

    if status_filter == "active":
        query = query.filter(Product.is_active.is_(True))
    elif status_filter == "unlisted":
        query = query.filter(Product.is_active.is_(False))

    products = query.order_by(Product.created_at.desc()).all()
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    total_products = Product.query.count()
    active_count = Product.query.filter_by(is_active=True).count()
    out_of_stock_count = Product.query.filter_by(stock=0).count()

    return render_template(
        "admin/store_products.html",
        products=products,
        categories=categories,
        filters=request.args,
        total_products=total_products,
        active_count=active_count,
        out_of_stock_count=out_of_stock_count,
    )


@admin_bp.route("/store/products/new", methods=["GET", "POST"])
@role_required("Admin")
def create_store_product():
    categories = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.name.asc()).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id", type=int)
        description = request.form.get("description", "").strip()
        price_raw = request.form.get("price", "").strip()
        stock_raw = request.form.get("stock", "").strip()
        is_active = "is_active" in request.form

        if not name:
            flash("Product name is required.", "danger")
            return render_template("admin/store_product_form.html", product=None, categories=categories, form_data=request.form)

        if not category_id or not ProductCategory.query.get(category_id):
            flash("Please select a valid active category.", "danger")
            return render_template("admin/store_product_form.html", product=None, categories=categories, form_data=request.form)

        if not description:
            flash("Product description is required.", "danger")
            return render_template("admin/store_product_form.html", product=None, categories=categories, form_data=request.form)

        try:
            price = Decimal(price_raw)
            if price <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            flash("Please enter a valid positive price.", "danger")
            return render_template("admin/store_product_form.html", product=None, categories=categories, form_data=request.form)

        try:
            stock = int(stock_raw)
            if stock < 0:
                raise ValueError()
        except (ValueError, TypeError):
            flash("Please enter a valid stock quantity (0 or greater).", "danger")
            return render_template("admin/store_product_form.html", product=None, categories=categories, form_data=request.form)

        image_name = None
        image_file = request.files.get("image")
        if image_file and image_file.filename:
            try:
                saved = save_upload(image_file, "product")
                if saved:
                    image_name = saved["stored_name"]
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("admin/store_product_form.html", product=None, categories=categories, form_data=request.form)

        product = Product(
            owner_id=g.user.id if hasattr(g, "user") and g.user else None,
            category_id=category_id,
            name=name,
            description=description,
            price=price,
            stock=stock,
            image=image_name,
            is_active=is_active,
        )
        db.session.add(product)
        db.session.commit()
        flash(f"Product '{product.name}' created successfully.", "success")
        return redirect(url_for("admin.store_products"))

    return render_template("admin/store_product_form.html", product=None, categories=categories, form_data={})


@admin_bp.route("/store/products/<int:product_id>/edit", methods=["GET", "POST"])
@role_required("Admin")
def edit_store_product(product_id):
    product = Product.query.get_or_404(product_id)
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category_id = request.form.get("category_id", type=int)
        description = request.form.get("description", "").strip()
        price_raw = request.form.get("price", "").strip()
        stock_raw = request.form.get("stock", "").strip()
        is_active = "is_active" in request.form

        if not name:
            flash("Product name is required.", "danger")
            return render_template("admin/store_product_form.html", product=product, categories=categories, form_data=request.form)

        if not category_id or not ProductCategory.query.get(category_id):
            flash("Please select a valid category.", "danger")
            return render_template("admin/store_product_form.html", product=product, categories=categories, form_data=request.form)

        if not description:
            flash("Product description is required.", "danger")
            return render_template("admin/store_product_form.html", product=product, categories=categories, form_data=request.form)

        try:
            price = Decimal(price_raw)
            if price <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            flash("Please enter a valid positive price.", "danger")
            return render_template("admin/store_product_form.html", product=product, categories=categories, form_data=request.form)

        try:
            stock = int(stock_raw)
            if stock < 0:
                raise ValueError()
        except (ValueError, TypeError):
            flash("Please enter a valid stock quantity (0 or greater).", "danger")
            return render_template("admin/store_product_form.html", product=product, categories=categories, form_data=request.form)

        image_file = request.files.get("image")
        if image_file and image_file.filename:
            try:
                saved = save_upload(image_file, "product")
                if saved:
                    product.image = saved["stored_name"]
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("admin/store_product_form.html", product=product, categories=categories, form_data=request.form)

        product.name = name
        product.category_id = category_id
        product.description = description
        product.price = price
        product.stock = stock
        product.is_active = is_active
        product.updated_at = datetime.utcnow()

        db.session.commit()
        flash(f"Product '{product.name}' updated successfully.", "success")
        return redirect(url_for("admin.store_products"))

    return render_template("admin/store_product_form.html", product=product, categories=categories, form_data={})


@admin_bp.post("/store/products/<int:product_id>/delete")
@role_required("Admin")
def delete_store_product(product_id):
    product = Product.query.get_or_404(product_id)
    product_name = product.name

    has_orders = OrderItem.query.filter_by(product_id=product.id).first() is not None
    if has_orders:
        product.is_active = False
        db.session.commit()
        flash(
            f"Product '{product_name}' has historical order records and cannot be permanently deleted. It has been deactivated and unlisted from the Store instead.",
            "warning",
        )
        return redirect(url_for("admin.store_products"))

    try:
        CartItem.query.filter_by(product_id=product.id).delete()

        if product.image:
            try:
                pub_base = Path(current_app.config["PUBLIC_UPLOAD_FOLDER"]).resolve()
                img_path = (pub_base / product.image).resolve()
                if img_path.is_file():
                    img_path.unlink(missing_ok=True)
            except Exception:
                pass

        db.session.delete(product)
        db.session.commit()
        flash(f"Product '{product_name}' was permanently deleted.", "success")
    except Exception:
        db.session.rollback()
        flash(f"Unable to delete '{product_name}' due to database constraints.", "danger")

    return redirect(url_for("admin.store_products"))


@admin_bp.post("/store/products/<int:product_id>/toggle")
@role_required("Admin")
def toggle_store_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    db.session.commit()
    status_label = "active and listed in the Store" if product.is_active else "unlisted from the Store"
    flash(f"Product '{product.name}' is now {status_label}.", "success")
    return redirect(url_for("admin.store_products"))


@admin_bp.post("/store/products/<int:product_id>/stock")
@role_required("Admin")
def update_store_product_stock(product_id):
    product = Product.query.get_or_404(product_id)
    stock_val = request.form.get("stock", type=int)
    if stock_val is None or stock_val < 0:
        flash("Stock quantity must be a non-negative number.", "danger")
    else:
        product.stock = stock_val
        db.session.commit()
        flash(f"Stock for '{product.name}' updated to {product.stock}.", "success")
    return redirect(url_for("admin.store_products"))

