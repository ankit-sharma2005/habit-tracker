"""
habits.py
=========
The dashboard and the habit CRUD routes.

    GET  /dashboard                     the dashboard (all habits + today's status)
    GET  /habits/new                    the "add habit" form
    POST /habits/new                    create the habit
    GET  /habits/<id>/edit              the "edit habit" form
    POST /habits/<id>/edit              save the changes
    POST /habits/<id>/delete            delete the habit and its history
    POST /habits/<id>/complete          mark it complete for today

Every route uses ``@login_required`` and every query is filtered by
``current_user.id``.  ``get_owned_habit()`` is the one place that decides
whether a habit belongs to the logged-in user, so ownership can never be
forgotten in a new route.
"""

from __future__ import annotations

from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

import stats
from models import Completion, Habit, db

habits_bp = Blueprint("habits", __name__)

# Limits used by the validation helper below.
MAX_NAME_LENGTH = 60
MAX_DESCRIPTION_LENGTH = 200
MAX_CATEGORY_LENGTH = 30
DEFAULT_CATEGORY = "General"
DEFAULT_TARGET_DAYS = 21
MAX_TARGET_DAYS = 365


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_owned_habit(habit_id: int) -> Habit:
    """Return the habit if it belongs to the logged-in user, else 404.

    Returning 404 rather than 403 is deliberate: it does not reveal whether
    a habit with that ID exists for somebody else.
    """
    habit = db.session.get(Habit, habit_id)
    if habit is None or habit.user_id != current_user.id:
        abort(404)
    return habit


def validate_habit_form(form) -> tuple[dict, list[str]]:
    """Validate the add/edit form.

    Returns ``(values, errors)`` where ``values`` holds the trimmed strings
    in the shape the template expects (so the form can be shown again with
    what the user typed) and ``errors`` is a list of friendly messages.
    """
    values = {
        "name": (form.get("name") or "").strip(),
        "description": (form.get("description") or "").strip(),
        "category": (form.get("category") or "").strip(),
        "start_date": (form.get("start_date") or "").strip(),
        "target_days": (form.get("target_days") or "").strip() or str(DEFAULT_TARGET_DAYS),
    }
    errors: list[str] = []

    # --- name ---
    if not values["name"]:
        errors.append("Habit name cannot be empty.")
    elif len(values["name"]) > MAX_NAME_LENGTH:
        errors.append(f"Habit name must be {MAX_NAME_LENGTH} characters or fewer.")

    # --- description (optional) ---
    if len(values["description"]) > MAX_DESCRIPTION_LENGTH:
        errors.append(
            f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer."
        )

    # --- category (blank means "General") ---
    if not values["category"]:
        values["category"] = DEFAULT_CATEGORY
    elif len(values["category"]) > MAX_CATEGORY_LENGTH:
        errors.append(f"Category must be {MAX_CATEGORY_LENGTH} characters or fewer.")

    # --- start date (blank means today) ---
    if values["start_date"]:
        try:
            start = date.fromisoformat(values["start_date"])
        except ValueError:
            errors.append("Please enter the start date as YYYY-MM-DD.")
        else:
            if start > date.today():
                errors.append("The start date cannot be in the future.")

    # --- target streak ---
    if not values["target_days"].isdigit():
        errors.append("Target streak must be a whole number of days.")
    elif not 1 <= int(values["target_days"]) <= MAX_TARGET_DAYS:
        errors.append(
            f"Target streak must be between 1 and {MAX_TARGET_DAYS} days."
        )

    return values, errors


def values_from_habit(habit: Habit) -> dict:
    """Turn a saved habit back into form values (used by the edit page)."""
    return {
        "name": habit.name,
        "description": habit.description,
        "category": habit.category,
        "start_date": habit.created_at.isoformat(),
        "target_days": str(habit.target_days),
    }


def parsed_start_date(values: dict) -> date:
    """Read the validated start date; a blank field means "today"."""
    text = values["start_date"]
    return date.fromisoformat(text) if text else date.today()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@habits_bp.get("/dashboard")
@login_required
def dashboard():
    """Show every habit of the logged-in user with today's status."""
    today = date.today()

    habits = (
        Habit.query.filter_by(user_id=current_user.id)
        .order_by(Habit.created_at, Habit.id)
        .all()
    )
    # One dictionary per habit, built by stats.py - the template stays dumb.
    cards = [stats.habit_summary(habit, today) for habit in habits]

    done_today = sum(1 for card in cards if card["done_today"])
    best_streak = max((card["current_streak"] for card in cards), default=0)
    average_week = (
        round(sum(card["weekly_percent"] for card in cards) / len(cards), 1)
        if cards
        else 0.0
    )

    return render_template(
        "dashboard.html",
        cards=cards,
        done_today=done_today,
        best_streak=best_streak,
        average_week=average_week,
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@habits_bp.route("/habits/new", methods=["GET", "POST"])
@login_required
def add():
    """Show the empty form, and create the habit when it is submitted."""
    values = {
        "name": "",
        "description": "",
        "category": "",
        "start_date": date.today().isoformat(),
        "target_days": str(DEFAULT_TARGET_DAYS),
    }

    if request.method == "POST":
        values, errors = validate_habit_form(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            habit = Habit(
                user_id=current_user.id,
                name=values["name"],
                description=values["description"],
                category=values["category"],
                target_days=int(values["target_days"]),
                created_at=parsed_start_date(values),
            )
            db.session.add(habit)
            db.session.commit()

            flash(f"'{habit.name}' was added.", "success")
            return redirect(url_for("habits.dashboard"))

    return render_template(
        "habit_form.html",
        title="Add a habit",
        subtitle="Give it a clear name and a target streak to work towards.",
        submit_label="Add habit",
        values=values,
        habit=None,
    )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@habits_bp.route("/habits/<int:habit_id>/edit", methods=["GET", "POST"])
@login_required
def edit(habit_id: int):
    """Show the form filled in with the habit's values, and save changes."""
    habit = get_owned_habit(habit_id)
    values = values_from_habit(habit)

    if request.method == "POST":
        values, errors = validate_habit_form(request.form)
        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            habit.name = values["name"]
            habit.description = values["description"]
            habit.category = values["category"]
            habit.target_days = int(values["target_days"])
            habit.created_at = parsed_start_date(values)
            db.session.commit()

            flash(f"'{habit.name}' was updated.", "success")
            return redirect(url_for("habits.dashboard"))

    return render_template(
        "habit_form.html",
        title=f"Edit {habit.name}",
        subtitle="Changing the start date re-calculates the percentages from that day.",
        submit_label="Save changes",
        values=values,
        habit=habit,
    )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@habits_bp.post("/habits/<int:habit_id>/delete")
@login_required
def delete(habit_id: int):
    """Delete a habit and, through the relationship cascade, its history.

    The confirmation popup is handled in the browser (static/js/main.js);
    because this is a POST route a stray link can never delete anything.
    """
    habit = get_owned_habit(habit_id)
    name = habit.name
    removed = habit.total_completions

    db.session.delete(habit)
    db.session.commit()

    flash(f"Deleted '{name}' and {removed} completion record(s).", "success")
    return redirect(url_for("habits.dashboard"))


# ---------------------------------------------------------------------------
# Mark complete for today
# ---------------------------------------------------------------------------

@habits_bp.post("/habits/<int:habit_id>/complete")
@login_required
def complete(habit_id: int):
    """Tick a habit for today. A second tick the same day is refused."""
    habit = get_owned_habit(habit_id)
    today = date.today()

    if today < habit.created_at:
        flash(
            f"'{habit.name}' starts on {habit.created_at:%d %b %Y}, "
            "so it cannot be completed today.",
            "warning",
        )
        return redirect(url_for("habits.dashboard"))

    if habit.is_completed_on(today):
        flash(f"'{habit.name}' is already marked complete for today.", "warning")
        return redirect(url_for("habits.dashboard"))

    db.session.add(Completion(habit_id=habit.id, completed_date=today))
    try:
        db.session.commit()
    except IntegrityError:
        # The UNIQUE(habit_id, completed_date) rule fired: a duplicate got in
        # between the check above and the insert.
        db.session.rollback()
        flash("That day is already recorded for this habit.", "warning")
        return redirect(url_for("habits.dashboard"))

    streak = stats.current_streak(habit, today)
    if streak >= habit.target_days:
        flash(
            f"🎉 {streak}-day streak for '{habit.name}' - "
            f"target of {habit.target_days} days reached!",
            "success",
        )
    else:
        flash(f"'{habit.name}' marked complete. Streak: {streak} day(s).", "success")

    return redirect(url_for("habits.dashboard"))
