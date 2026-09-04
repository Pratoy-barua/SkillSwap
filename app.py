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
