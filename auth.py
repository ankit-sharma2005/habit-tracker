"""
auth.py
=======
Registration, login and logout.

Everything a visitor needs before they can see any habit lives here:

    GET  /register   show the registration form
    POST /register   create the account
    GET  /login      show the login form
    POST /login      check the password and start the session
    POST /logout     end the session

Passwords are hashed by ``User.set_password`` (werkzeug.security) and only
the hash is written to the database.  ``login_user`` from Flask-Login stores
the user's ID in a signed session cookie, which is how later requests know
who is asking.
"""

from __future__ import annotations

import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from models import User, db

auth_bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8
MAX_USERNAME_LENGTH = 40
MAX_EMAIL_LENGTH = 120

# Usernames: letters, numbers, dot, dash and underscore, 3-40 characters.
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,40}$")
# A deliberately simple email check - good enough to catch typos without
# rejecting valid addresses (the only real test is sending an email).
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_registration(username: str, email: str, password: str, confirm: str) -> list[str]:
    """Check the registration form and return a list of error messages.

    An empty list means the form is valid.  Each message is written for the
    person filling in the form, not for a developer.
    """
    errors: list[str] = []

    # --- username ---
    if not username:
        errors.append("Username is required.")
    elif not USERNAME_PATTERN.match(username):
        errors.append(
            "Username must be 3-40 characters and may only contain letters, "
            "numbers, dots, dashes and underscores."
        )

    # --- email ---
    if not email:
        errors.append("Email is required.")
    elif len(email) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.match(email):
        errors.append("Please enter a valid email address, e.g. you@example.com.")

    # --- password ---
    if not password:
        errors.append("Password is required.")
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    elif password != confirm:
        errors.append("The two passwords do not match.")

    # --- uniqueness (case-insensitive) ---
    if username:
        existing = User.query.filter(func.lower(User.username) == username.lower()).first()
        if existing is not None:
            errors.append("That username is already taken.")

    if email:
        existing = User.query.filter(func.lower(User.email) == email.lower()).first()
        if existing is not None:
            errors.append("An account with that email already exists.")

    return errors


def _safe_next(target: str | None) -> str | None:
    """Return ``target`` only when it is a local path, else ``None``.

    This blocks "open redirect" tricks such as ``?next=https://evil.example``
    where an attacker tries to bounce the user to another website after login.
    """
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Show the registration form and create the account on POST."""
    if current_user.is_authenticated:
        return redirect(url_for("habits.dashboard"))

    values = {"username": "", "email": ""}

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        values["username"], values["email"] = username, email

        errors = validate_registration(username, email, password, confirm)
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("register.html", values=values)

        user = User(username=username, email=email)
        user.set_password(password)  # stores the hash, never the password
        db.session.add(user)
        db.session.commit()

        flash(f"Account created for {username}. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", values=values)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Show the login form and start a session on POST."""
    if current_user.is_authenticated:
        return redirect(url_for("habits.dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""

        if not identifier or not password:
            flash("Please enter your username (or email) and password.", "danger")
            return render_template("login.html", identifier=identifier)

        # Allow logging in with either the username or the email address.
        user = User.query.filter(
            (func.lower(User.username) == identifier.lower())
            | (func.lower(User.email) == identifier.lower())
        ).first()

        # The same message for "no such user" and "wrong password" avoids
        # telling an attacker which usernames exist.
        if user is None or not user.check_password(password):
            flash("Incorrect username, email or password.", "danger")
            return render_template("login.html", identifier=identifier)

        login_user(user, remember=bool(request.form.get("remember")))
        flash(f"Welcome back, {user.username}!", "success")

        return redirect(_safe_next(request.form.get("next")) or url_for("habits.dashboard"))

    return render_template("login.html", identifier="")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@auth_bp.post("/logout")
@login_required
def logout():
    """End the session. It is a POST route so a link cannot log you out."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
