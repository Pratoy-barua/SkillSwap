"""SkillSwap store, carts, orders, and order items."""

from datetime import datetime

from extensions import db


class ProductCategory(db.Model):
    __tablename__ = "product_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    products = db.relationship("Product", back_populates="category")


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("product_categories.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    image = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner = db.relationship("User")
    category = db.relationship("ProductCategory", back_populates="products")
    order_items = db.relationship("OrderItem", back_populates="product")


class Cart(db.Model):
    __tablename__ = "carts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    user = db.relationship("User")
    items = db.relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(db.Model):
    __tablename__ = "cart_items"
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    cart = db.relationship("Cart", back_populates="items")
    product = db.relationship("Product")
    __table_args__ = (db.UniqueConstraint("cart_id", "product_id", name="uq_cart_product"),)


class Order(db.Model):
    __tablename__ = "orders"
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_reference = db.Column(db.String(80), unique=True, nullable=True)
    payment_status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    order_status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    platform_commission = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    seller_earning = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    delivery_address = db.Column(db.String(255), nullable=False)
    delivery_phone = db.Column(db.String(40), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    buyer = db.relationship("User")
    items = db.relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = db.Column(db.String(180), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    order = db.relationship("Order", back_populates="items")
    product = db.relationship("Product", back_populates="order_items")
