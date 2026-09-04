"""Small security helpers shared by forms and routes."""

import secrets


def issue_csrf_token(session):
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]
