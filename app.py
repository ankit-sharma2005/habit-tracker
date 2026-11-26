"""
app.py
======
The entry point of the Habit Tracker web application.

What happens here
-----------------
1. ``create_app()`` builds and configures the Flask application object.
2. The database and Flask-Login are connected to it.
3. Three blueprints are registered - auth, habits and streaks - so the code
   is split into small files instead of one huge app.py.
4. ``db.create_all()`` creates the tables on first run.

Run it with:

    python app.py            # http://127.0.0.1:5000
    PORT=8000 python app.py  # another port

All habit and streak routes are protected with ``@login_required`` inside
their own blueprint files, and every query is filtered by ``user_id`` so one
user can never see another user's data.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

from flask import Flask, redirect, render_template, url_for
from flask_login import LoginManager, current_user

from models import db, User

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "habits.db"
DEFAULT_PORT = 5000


def create_app() -> Flask:
    """Build the Flask application, wire everything together and return it."""
    app = Flask(__name__)

    app.config.update(
        # In production this must come from an environment variable so the
        # value stays secret; the default is only for local development.
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-key-change-me"),
        # SQLAlchemy needs forward slashes, also on Windows.
        SQLALCHEMY_DATABASE_URI="sqlite:///" + DATABASE_PATH.as_posix(),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Browser-side hardening for the session cookie.
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    # -- database -----------------------------------------------------------
    db.init_app(app)

    # -- login manager ------------------------------------------------------
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # where @login_required sends guests
    login_manager.login_message = "Please log in to see your habits."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        """Turn the ID stored in the session back into a User object."""
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    # -- blueprints ---------------------------------------------------------
    from auth import auth_bp
    from habits import habits_bp
    from streaks import streaks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(habits_bp)
    app.register_blueprint(streaks_bp)

    # -- shared template values --------------------------------------------
    @app.context_processor
    def inject_globals() -> dict:
        """Make ``today`` available in every template."""
        return {"today": date.today()}

    # -- routes -------------------------------------------------------------
    @app.get("/")
    def index():
        """Send visitors to their dashboard, or to the login page."""
        if current_user.is_authenticated:
            return redirect(url_for("habits.dashboard"))
        return redirect(url_for("auth.login"))

    # -- error pages --------------------------------------------------------
    @app.errorhandler(404)
    def not_found(error):
        """Shown for an unknown address or another user's habit ID."""
        return render_template("404.html"), 404

    # Create the tables the first time the app starts.
    with app.app_context():
        db.create_all()

    return app


# ``flask --app app run`` and ``python app.py`` both use this object.
app = create_app()


if __name__ == "__main__":
    # python app.py        -> http://127.0.0.1:5000
    # python app.py 8000   -> http://127.0.0.1:8000
    port = DEFAULT_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            raise SystemExit("Usage: python app.py [port]   e.g. python app.py 5000")

    app.run(host="127.0.0.1", port=port, debug=False)
