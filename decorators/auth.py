"""Session and role guards."""

from functools import wraps

from flask import abort, g, jsonify, redirect, request, session, url_for

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
            if request.path.startswith("/api/") and (request.is_json or request.headers.get("Accept") == "application/json" or request.headers.get("X-Requested-With") == "XMLHttpRequest"):
                return jsonify({
                    "error": "Authentication required. Please log in to access this feature.",
                    "login_url": url_for("auth.login", next=url_for("discovery.mentor_search"))
                }), 401

            next_target = url_for("discovery.mentor_search") if request.path.startswith("/api/") else (request.full_path if request.query_string else request.path)
            return redirect(url_for("auth.login", next=next_target))
        if user.account_status != "Approved" and user.role.name != "Admin":
            if request.path.startswith("/api/"):
                return jsonify({"error": "Account pending approval."}), 403
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


def authenticated_role(*roles):
    """Allows authenticated users in given roles to access views like notifications regardless of account status."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = load_user()
            if not user:
                return redirect(url_for("auth.login"))
            if user.role.name not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
