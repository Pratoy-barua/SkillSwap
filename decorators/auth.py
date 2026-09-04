"""Session and role guards."""

from functools import wraps

from flask import abort, g, redirect, session, url_for

from models.auth import User


def load_user():
    user_id = session.get("user_id")
    g.current_user = User.query.get(user_id) if user_id else None
    return g.current_user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = load_user()
        if not user:
            return redirect(url_for("auth.login"))
        if user.account_status in {"Rejected", "Suspended"}:
            session.clear()
            return redirect(url_for("auth.account_status", status=user.account_status))
        if user.account_status != "Approved" and user.role.name != "Admin":
            return redirect(url_for("auth.account_status", status=user.account_status))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.current_user.role.name not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
