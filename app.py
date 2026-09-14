"""Application entry point for SkillSwap."""

import os
from flask import Flask, abort, render_template, request, session

from config import config_by_name
from extensions import db


def create_app(config_name=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    selected_config = config_name or os.getenv("FLASK_ENV", "development")
    app.config.from_object(config_by_name.get(selected_config, config_by_name["development"]))

    db.init_app(app)

    # Import models before CLI/table creation so SQLAlchemy sees every table.
    import models  # noqa: F401

    @app.before_request
    def csrf_guard():
        from decorators.auth import load_user

        load_user()
        if request.method == "POST" and request.form.get("csrf_token") != session.get("csrf_token"):
            abort(400, description="Invalid or missing CSRF token.")

    @app.context_processor
    def security_context():
        from services.security import issue_csrf_token
        from flask import g

        user = getattr(g, "current_user", None)
        unread_notifications = []
        if user:
            try:
                from models.connection import Notification

                unread_notifications = Notification.query.filter_by(user_id=user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
            except Exception:
                unread_notifications = []
        return {"csrf_token": issue_csrf_token(session), "current_user": user, "unread_notifications": unread_notifications}

    from routes.public import public_bp
    from routes.auth import auth_bp
    from routes.profiles import learner_bp, mentor_bp
    from routes.admin import admin_bp
    from routes.discovery import discovery_bp
    from routes.connections import connection_bp
    from routes.learning import learning_bp
    from routes.payments import payment_bp
    from routes.store import store_bp
    from routes.reviews import reviews_bp
    from routes.premium import premium_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(learner_bp)
    app.register_blueprint(mentor_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(discovery_bp)
    app.register_blueprint(connection_bp)
    app.register_blueprint(learning_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(store_bp)
    app.register_blueprint(reviews_bp)
    app.register_blueprint(premium_bp)

    @app.errorhandler(403)
    def forbidden(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template("errors/500.html"), 500

    @app.cli.command("init-db")
    def init_db_command():
        """Create the Phase 2 tables without deleting existing data."""
        db.create_all()
        upgrade_phase3_schema()
        print("SkillSwap database tables are ready.")

    @app.cli.command("upgrade-db")
    def upgrade_db_command():
        """Add Phase 3 columns to an existing Phase 2 database without deleting data."""
        db.create_all()
        upgrade_phase3_schema()
        print("SkillSwap database schema is upgraded.")

    def upgrade_phase3_schema():
        from sqlalchemy import inspect, text

        additions = {
            "users": {"address": "VARCHAR(255) NOT NULL DEFAULT ''"},
            "skills": {"is_active": "BOOLEAN NOT NULL DEFAULT 1", "icon": "VARCHAR(255) NULL"},
            "mentor_profiles": {"rating": "DECIMAL(3,2) NOT NULL DEFAULT 0"},
            "subscriptions": {"premium_plan_id": "INTEGER NULL"},
            "mentor_skills": {
                "experience": "VARCHAR(120) NULL",
                "is_paid": "BOOLEAN NOT NULL DEFAULT 0",
                "price": "DECIMAL(10,2) NULL",
                "pricing_type": "VARCHAR(30) NOT NULL DEFAULT 'Course-based'",
            },
            # Phase 4: professional profile details
            "learner_profiles": {
                "occupation": "VARCHAR(120) NULL",
                "date_of_birth": "DATE NULL",
                "gender": "VARCHAR(20) NULL",
                "linkedin_url": "VARCHAR(255) NULL",
                "github_url": "VARCHAR(255) NULL",
                "website_url": "VARCHAR(255) NULL",
            },
        }
        # mentor_profiles professional detail columns (merged separately to avoid
        # overwriting the existing dict key above)
        mentor_pro_columns = {
            "occupation": "VARCHAR(120) NULL",
            "date_of_birth": "DATE NULL",
            "gender": "VARCHAR(20) NULL",
            "linkedin_url": "VARCHAR(255) NULL",
            "github_url": "VARCHAR(255) NULL",
            "website_url": "VARCHAR(255) NULL",
        }
        inspector = inspect(db.engine)
        dialect = db.engine.dialect.name
        preparer = db.engine.dialect.identifier_preparer
        for table, columns in additions.items():
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    quoted_table = preparer.quote(table)
                    quoted_column = preparer.quote(name)
                    db.session.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_column} {definition}"))
        # Apply mentor_profiles professional columns
        existing_mentor_cols = {column["name"] for column in inspector.get_columns("mentor_profiles")}
        for name, definition in mentor_pro_columns.items():
            if name not in existing_mentor_cols:
                db.session.execute(text(f"ALTER TABLE `mentor_profiles` ADD COLUMN `{name}` {definition}"))
        db.session.commit()


    @app.cli.command("seed-admin")
    def seed_admin_command():
        """Create or update the admin from ADMIN_EMAIL/ADMIN_PASSWORD environment variables."""
        from models.auth import Role, User

        email = os.getenv("ADMIN_EMAIL")
        password = os.getenv("ADMIN_PASSWORD")
        if not email or not password or len(password) < 12:
            raise RuntimeError("Set ADMIN_EMAIL and an ADMIN_PASSWORD of at least 12 characters.")
        role = Role.query.filter_by(name="Admin").first()
        if not role:
            role = Role(name="Admin")
            db.session.add(role)
            db.session.flush()
        user = User.query.filter_by(email=email.lower()).first()
        if not user:
            user = User(role=role, full_name="SkillSwap Administrator", email=email.lower(), phone="admin", account_status="Approved")
            db.session.add(user)
        user.role = role
        user.account_status = "Approved"
        user.set_password(password)
        db.session.commit()
        print(f"Admin account ready: {user.email}")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Add idempotent demo skills, mentor profiles, and store products."""
        from decimal import Decimal

        from models.auth import Location, MentorProfile, MentorSkill, Role, Skill, User
        from models.store import Product, ProductCategory

        db.create_all()
        mentor_role = Role.query.filter_by(name="Mentor").first()
        if not mentor_role:
            mentor_role = Role(name="Mentor")
            db.session.add(mentor_role)
            db.session.flush()

        skill_names = [
            "Programming / Coding",
            "Web Development",
            "App Development",
            "Graphic Design",
            "UI/UX Design",
            "Digital Marketing",
            "SEO",
            "Video Editing",
            "Photography",
            "Videography",
            "Microsoft Excel",
            "Microsoft Office",
            "Data Analysis",
            "English",
            "Public Speaking",
            "Content Writing",
            "Social Media Management",
            "Freelancing",
            "Guitar",
            "Piano / Keyboard",
            "Singing",
            "Drawing / Sketching",
            "Painting",
            "Cooking",
            "Baking",
            "Driving",
            "Cycling",
            "Swimming",
            "Fitness / Gym",
            "Language Learning",
            "Spoken English",
        ]
        skills = {}
        for name in skill_names:
            skill = Skill.query.filter_by(name=name).first()
            if not skill:
                skill = Skill(name=name, is_active=True)
                db.session.add(skill)
                db.session.flush()
            skills[name] = skill

        mentors = [
            {"name": "Nusrat Jahan", "email": "demo.nusrat@skillswap.local", "city": "Dhaka", "area": "Notunbazar", "bio": "Practical graphic design guidance for beginners and aspiring freelancers.", "experience": "5 years", "teaching_type": "Online and in person", "skill": "Graphic Design", "paid": True, "price": Decimal("800"), "rating": Decimal("4.80"), "image": "demo-mentor-nusrat.png"},
            {"name": "Tanvir Rahman", "email": "demo.tanvir@skillswap.local", "city": "Dhaka", "area": "Dhanmondi", "bio": "Learn photography fundamentals, composition, and mobile editing techniques.", "experience": "4 years", "teaching_type": "In person", "skill": "Photography", "paid": False, "price": Decimal("0"), "rating": Decimal("4.60"), "image": "demo-mentor-tanvir.png"},
            {"name": "Sadia Islam", "email": "demo.sadia@skillswap.local", "city": "Dhaka", "area": "Uttara", "bio": "Build confidence in spoken English through friendly, structured practice.", "experience": "6 years", "teaching_type": "Online", "skill": "Spoken English", "paid": True, "price": Decimal("600"), "rating": Decimal("4.90"), "image": "demo-mentor-sadia.png"},
            {"name": "Arif Hossain", "email": "demo.arif@skillswap.local", "city": "Dhaka", "area": "Mirpur", "bio": "Start web development with HTML, CSS, and practical project guidance.", "experience": "3 years", "teaching_type": "Online and in person", "skill": "Web Development", "paid": True, "price": Decimal("1000"), "rating": Decimal("4.70"), "image": "demo-mentor-arif.png"},
        ]
        for item in mentors:
            location = Location.query.filter_by(city=item["city"], area=item["area"], country="Bangladesh").first()
            if not location:
                location = Location(city=item["city"], area=item["area"], country="Bangladesh")
                db.session.add(location)
                db.session.flush()
            user = User.query.filter_by(email=item["email"]).first()
            if not user:
                user = User(role=mentor_role, full_name=item["name"], email=item["email"], phone="01700000000", address=f'{item["area"]}, {item["city"]}', account_status="Approved", location=location)
                user.set_password("DemoPass123!")
                db.session.add(user)
                db.session.flush()
            if not user.profile_photo:
                user.profile_photo = item["image"]
            profile = user.mentor_profile
            if not profile:
                profile = MentorProfile(user=user, bio=item["bio"], experience=item["experience"], teaching_type=item["teaching_type"], is_paid=item["paid"], pricing=item["price"], rating=item["rating"])
                db.session.add(profile)
                db.session.flush()
            mentor_skill = MentorSkill.query.filter_by(mentor_profile_id=profile.id, skill_id=skills[item["skill"]].id).first()
            if not mentor_skill:
                db.session.add(MentorSkill(mentor_profile=profile, skill=skills[item["skill"]], experience=item["experience"], is_paid=item["paid"], price=item["price"], pricing_type="Course-based"))

        products = [
            ("Learning supplies", "A5 Study Notebook", "A compact notebook for course notes, learning plans, and daily practice.", Decimal("180"), 25, "demo-product-notebook.png"),
            ("Creative tools", "Sketching Pencil Set", "A practical pencil set for drawing, design exercises, and creative practice.", Decimal("350"), 18, "demo-product-pencils.png"),
            ("Tech accessories", "Laptop Stand", "An adjustable desk stand for comfortable online learning sessions.", Decimal("1200"), 12, "demo-product-laptop-stand.png"),
        ]
        for category_name, name, description, price, stock, image in products:
            category = ProductCategory.query.filter_by(name=category_name).first()
            if not category:
                category = ProductCategory(name=category_name, is_active=True)
                db.session.add(category)
                db.session.flush()
            product = Product.query.filter_by(name=name).first()
            if not product:
                db.session.add(Product(category=category, name=name, description=description, price=price, stock=stock, image=image, is_active=True))
            elif not product.image:
                product.image = image

        db.session.commit()
        print("Demo skills, mentors, and store products are ready.")

    @app.cli.command("check-db")
    def check_db_command():
        """Verify that the configured database is reachable."""
        from sqlalchemy import text

        try:
            with db.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as error:
            raise RuntimeError(
                "MySQL is not reachable. Start MySQL or run `docker compose up db`."
            ) from error
        print("Database connection successful.")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config["DEBUG"])
