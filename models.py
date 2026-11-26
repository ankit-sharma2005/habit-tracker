"""
models.py
=========
The database layer of the Habit Tracker.

Every table is a class that inherits from ``db.Model`` (Flask-SQLAlchemy).
Because SQLAlchemy is an ORM ("Object Relational Mapper") we never write
INSERT / SELECT by hand - we create Python objects and let SQLAlchemy turn
them into SQL.

Tables
------
users        id, username, email, password_hash, created_at
habits       id, user_id (FK -> users.id), name, description, category,
             target_days, created_at  (created_at holds the START DATE)
completions  id, habit_id (FK -> habits.id), completed_date,
             UNIQUE(habit_id, completed_date)

Security note
-------------
The ``password_hash`` column never stores the real password.  The user's
password is turned into a one-way hash by ``werkzeug.security``; logging in
re-computes the hash of what was typed and compares the two.  Even someone
who copies the database file cannot read the passwords.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
from werkzeug.security import check_password_hash, generate_password_hash

# The single SQLAlchemy object shared by the whole application.
# app.py calls db.init_app(app); every model below is registered on it.
db = SQLAlchemy()


# ---------------------------------------------------------------------------
# SQLite settings
# ---------------------------------------------------------------------------

@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    """Switch on foreign-key checking for every new SQLite connection.

    SQLite ignores FOREIGN KEY / ON DELETE CASCADE rules unless they are
    enabled per connection, which is easy to forget.  Registering this
    listener once here means the rules always apply.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------

class User(UserMixin, db.Model):
    """A registered person.  One user owns many habits.

    ``UserMixin`` comes from Flask-Login and supplies the methods it needs
    (``is_authenticated``, ``get_id`` and friends), so we only add the
    password helpers.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.Date, nullable=False, default=date.today)

    # Deleting a user deletes their habits too, and (through the habit
    # relationship below) every completion those habits had.
    habits = db.relationship(
        "Habit",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # -- password handling --------------------------------------------------

    def set_password(self, password: str) -> None:
        """Store a salted hash of ``password`` - never the plain text."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return ``True`` when ``password`` matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:  # helps while debugging
        return f"<User {self.id} {self.username!r}>"


# ---------------------------------------------------------------------------
# habits
# ---------------------------------------------------------------------------

class Habit(db.Model):
    """One habit such as "Morning jog", owned by exactly one user.

    ``created_at`` stores the habit's START DATE.  The statistics use it as
    the first day the habit could possibly have been completed, so a habit
    started three days ago is not punished with "0 out of 30".
    """

    __tablename__ = "habits"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = db.Column(db.String(60), nullable=False)
    description = db.Column(db.String(200), nullable=False, default="")
    category = db.Column(db.String(30), nullable=False, default="General")
    target_days = db.Column(db.Integer, nullable=False, default=21)
    created_at = db.Column(db.Date, nullable=False, default=date.today, index=True)

    owner = db.relationship("User", back_populates="habits")
    completions = db.relationship(
        "Completion",
        back_populates="habit",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="Completion.completed_date",
    )

    # -- small helpers used by the views and by stats.py --------------------

    def is_completed_on(self, day: date) -> bool:
        """Return ``True`` when this habit is already ticked on ``day``."""
        return self.completions.filter_by(completed_date=day).first() is not None

    def completion_dates(self) -> set[date]:
        """Return the set of days this habit was completed on."""
        return {completion.completed_date for completion in self.completions}

    @property
    def total_completions(self) -> int:
        """Return how many completion records this habit has."""
        return self.completions.count()

    def __repr__(self) -> str:
        return f"<Habit {self.id} {self.name!r}>"


# ---------------------------------------------------------------------------
# completions
# ---------------------------------------------------------------------------

class Completion(db.Model):
    """One "habit X was done on day Y" record.

    The UNIQUE constraint is what makes a duplicate impossible: even if two
    requests arrive at the same moment, the database refuses the second row.
    """

    __tablename__ = "completions"
    __table_args__ = (
        db.UniqueConstraint("habit_id", "completed_date", name="uq_completion_per_day"),
    )

    id = db.Column(db.Integer, primary_key=True)
    habit_id = db.Column(
        db.Integer,
        db.ForeignKey("habits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    completed_date = db.Column(db.Date, nullable=False, index=True)

    habit = db.relationship("Habit", back_populates="completions")

    def __repr__(self) -> str:
        return f"<Completion habit={self.habit_id} {self.completed_date}>"


# ---------------------------------------------------------------------------
# The raw SQL these models create
# ---------------------------------------------------------------------------
# Kept here as a comment so the report can quote it.  Flask-SQLAlchemy runs
# exactly this DDL when db.create_all() is called:
#
#   CREATE TABLE users (
#       id            INTEGER PRIMARY KEY AUTOINCREMENT,
#       username      VARCHAR(40)  NOT NULL UNIQUE,
#       email         VARCHAR(120) NOT NULL UNIQUE,
#       password_hash VARCHAR(255) NOT NULL,
#       created_at    DATE NOT NULL
#   );
#
#   CREATE TABLE habits (
#       id          INTEGER PRIMARY KEY AUTOINCREMENT,
#       user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
#       name        VARCHAR(60)  NOT NULL,
#       description VARCHAR(200) NOT NULL,
#       category    VARCHAR(30)  NOT NULL,
#       target_days INTEGER      NOT NULL,
#       created_at  DATE         NOT NULL
#   );
#
#   CREATE TABLE completions (
#       id             INTEGER PRIMARY KEY AUTOINCREMENT,
#       habit_id       INTEGER NOT NULL REFERENCES habits (id) ON DELETE CASCADE,
#       completed_date DATE NOT NULL,
#       CONSTRAINT uq_completion_per_day UNIQUE (habit_id, completed_date)
#   );
