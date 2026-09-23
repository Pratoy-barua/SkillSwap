"""Dynamic store, owner products, cart, checkout, and order history."""

from decimal import Decimal, InvalidOperation

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import and_, or_

from decorators.auth import role_required
from extensions import db
from models.learning import PlatformSetting
from models.store import Cart, CartItem, Order, OrderItem, Product, ProductCategory
from services.notifications import notify
from services.payments import DemoPaymentProvider, split_amount
from services.revenue import record_revenue
from services.uploads import save_upload


store_bp = Blueprint("store", __name__, url_prefix="/store")


def cart_for_user():
    cart = Cart.query.filter_by(user_id=g.current_user.id).first()
    if not cart:
        cart = Cart(user_id=g.current_user.id)
        db.session.add(cart)
        db.session.flush()
    return cart


def product_form(product=None):
    categories = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.name).all()
    return render_template("store/product_form.html", product=product, categories=categories)


@store_bp.get("/")
def index():
    search = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", type=int)
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    availability = request.args.get("availability", "")
    query = Product.query.join(Product.category).filter(Product.is_active.is_(True), ProductCategory.is_active.is_(True))
    if search:
        query = query.filter(or_(Product.name.ilike(f"%{search}%"), Product.description.ilike(f"%{search}%")))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)
    if availability == "available":
        query = query.filter(Product.stock > 0)
    elif availability == "out":
        query = query.filter(Product.stock <= 0)
    try:
        products = query.order_by(Product.created_at.desc()).all()
        categories = ProductCategory.query.filter_by(is_active=True).order_by(ProductCategory.name).all()
    except Exception:
        products, categories = [], []
    return render_template("store/index.html", products=products, categories=categories, filters=request.args)


@store_bp.get("/products/<int:product_id>")
def details(product_id):
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    return render_template("store/details.html", product=product)


@store_bp.route("/products/new", methods=["GET", "POST"])
@role_required("Learner", "Mentor", "Admin")
def create_product():
    if request.method == "POST":
        try:
            price = Decimal(request.form.get("price", "0"))
            stock = int(request.form.get("stock", "0"))
            category_id = int(request.form.get("category_id", "0"))
        except (InvalidOperation, TypeError, ValueError):
            flash("Price, stock, and category must be valid.", "danger")
            return product_form()
        category = ProductCategory.query.filter_by(id=category_id, is_active=True).first()
        if not category or price < 0 or stock < 0 or not request.form.get("name", "").strip() or not request.form.get("description", "").strip():
            flash("Complete valid product information.", "danger")
            return product_form()
        image = None
        if request.files.get("image") and request.files["image"].filename:
            try:
                image = save_upload(request.files["image"], "product")["stored_name"]
            except ValueError as error:
                flash(str(error), "danger")
                return product_form()
        product = Product(owner_id=None if g.current_user.role.name == "Admin" else g.current_user.id, category_id=category.id, name=request.form["name"].strip()[:180], description=request.form["description"].strip(), price=price, stock=stock, image=image, is_active=True)
        db.session.add(product)
        db.session.commit()
        flash("Product created.", "success")
        return redirect(url_for("store.details", product_id=product.id))
    return product_form()


@store_bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@role_required("Learner", "Mentor", "Admin")
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if g.current_user.role.name != "Admin" and product.owner_id != g.current_user.id:
        abort(403)
    if request.method == "POST":
        try:
            product.price = Decimal(request.form.get("price", "0"))
            product.stock = int(request.form.get("stock", "0"))
            product.category_id = int(request.form.get("category_id", "0"))
        except (InvalidOperation, TypeError, ValueError):
            flash("Price, stock, and category must be valid.", "danger")
            return product_form(product)
        if product.price < 0 or product.stock < 0 or not ProductCategory.query.filter_by(id=product.category_id, is_active=True).first():
            flash("Invalid product values.", "danger")
            return product_form(product)
        product.name = request.form.get("name", "").strip()[:180]
        product.description = request.form.get("description", "").strip()
        if request.files.get("image") and request.files["image"].filename:
            try:
                product.image = save_upload(request.files["image"], "product")["stored_name"]
            except ValueError as error:
                flash(str(error), "danger")
                return product_form(product)
        db.session.commit()
        flash("Product updated.", "success")
        return redirect(url_for("store.details", product_id=product.id))
    return product_form(product)


@store_bp.post("/products/<int:product_id>/toggle")
@role_required("Learner", "Mentor", "Admin")
def toggle_product(product_id):
    product = Product.query.get_or_404(product_id)
    if g.current_user.role.name != "Admin" and product.owner_id != g.current_user.id:
        abort(403)
    product.is_active = not product.is_active
    db.session.commit()
    flash("Product availability updated.", "success")
    return redirect(url_for("store.details", product_id=product.id))


@store_bp.post("/cart/add/<int:product_id>")
@role_required("Learner", "Mentor")
def add_to_cart(product_id):
    product = Product.query.filter_by(id=product_id, is_active=True).first_or_404()
    quantity = request.form.get("quantity", 1, type=int)
    if quantity < 1 or product.stock < quantity:
        flash("That quantity is not available.", "danger")
        return redirect(url_for("store.details", product_id=product.id))
    cart = cart_for_user()
    item = CartItem.query.filter_by(cart_id=cart.id, product_id=product.id).first()
    if item:
        if item.quantity + quantity > product.stock:
            flash("Cart quantity cannot exceed current stock.", "danger")
            return redirect(url_for("store.cart"))
        item.quantity += quantity
    else:
        db.session.add(CartItem(cart=cart, product=product, quantity=quantity))
    db.session.commit()
    flash("Product added to cart.", "success")
    return redirect(url_for("store.cart"))


@store_bp.get("/cart")
@role_required("Learner", "Mentor")
def cart():
    cart = cart_for_user()
    subtotal = sum((item.product.price * item.quantity for item in cart.items), Decimal("0"))
    return render_template("store/cart.html", cart=cart, subtotal=subtotal)


@store_bp.post("/cart/items/<int:item_id>/<action>")
@role_required("Learner", "Mentor")
def update_cart_item(item_id, action):
    item = CartItem.query.join(Cart).filter(CartItem.id == item_id, Cart.user_id == g.current_user.id).first_or_404()
    if action == "remove":
        db.session.delete(item)
    elif action in {"increase", "decrease"}:
        item.quantity += 1 if action == "increase" else -1
        if action == "increase" and item.quantity > item.product.stock:
            item.quantity = item.product.stock
            flash("Quantity capped at available stock.", "warning")
        if item.quantity <= 0:
            db.session.delete(item)
    else:
        abort(404)
    db.session.commit()
    return redirect(url_for("store.cart"))


@store_bp.route("/checkout", methods=["GET", "POST"])
@role_required("Learner", "Mentor")
def checkout():
    cart = cart_for_user()
    items = list(cart.items)
    if not items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for("store.index"))
    if request.method == "POST":
        for item in items:
            if not item.product.is_active or item.product.stock < item.quantity:
                flash(f"{item.product.name} is no longer available in that quantity.", "danger")
                return redirect(url_for("store.cart"))
        subtotal = sum((item.product.price * item.quantity for item in items), Decimal("0"))
        total, commission, seller_earning = split_amount(subtotal, db.session)
        outcome = request.form.get("demo_outcome", "success")
        result = DemoPaymentProvider().charge(total, outcome if outcome in {"success", "failure"} else "failure")
        order = Order(buyer_id=g.current_user.id, total_amount=total, payment_reference=result["reference_id"], payment_status=result["status"], order_status="Processing" if result["status"] == "Successful" else "Cancelled", platform_commission=commission, seller_earning=seller_earning, delivery_address=request.form.get("delivery_address", "").strip()[:255], delivery_phone=request.form.get("delivery_phone", "").strip()[:40])
        if not order.delivery_address or not order.delivery_phone:
            flash("Delivery address and phone are required.", "danger")
            return render_template("store/checkout.html", cart=cart, subtotal=subtotal)
        db.session.add(order)
        db.session.flush()
        if result["status"] == "Successful":
            record_revenue("Store Order", order.id, order.total_amount, order.platform_commission, order.seller_earning)
        for item in items:
            db.session.add(OrderItem(order=order, product_id=item.product.id, product_name=item.product.name, quantity=item.quantity, unit_price=item.product.price, subtotal=item.product.price * item.quantity))
            if result["status"] == "Successful":
                item.product.stock -= item.quantity
        if result["status"] == "Successful":
            cart.items.clear()
            notify(g.current_user.id, "order_status", "Order Placed", f"Order #{order.id} is being processed.", "order", order.id)
        else:
            notify(g.current_user.id, "order_status", "Order Cancelled", f"Order #{order.id} could not be completed due to payment failure.", "order", order.id)
        db.session.commit()
        return redirect(url_for("store.order_details", order_id=order.id))
    subtotal = sum((item.product.price * item.quantity for item in items), Decimal("0"))
    return render_template("store/checkout.html", cart=cart, subtotal=subtotal)


@store_bp.get("/orders")
@role_required("Learner", "Mentor")
def orders():
    return render_template("store/orders.html", orders=Order.query.filter_by(buyer_id=g.current_user.id).order_by(Order.created_at.desc()).all())


@store_bp.get("/orders/<int:order_id>")
@role_required("Learner", "Mentor", "Admin")
def order_details(order_id):
    order = Order.query.get_or_404(order_id)
    if g.current_user.role.name != "Admin" and order.buyer_id != g.current_user.id:
        abort(403)
    return render_template("store/order_details.html", order=order)
