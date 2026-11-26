"""
streaks.py
==========
The streak page - the main feature of the project.

    GET  /streaks              the page (habit dropdown, 30-day grid, charts)
    POST /streaks/add          add a completion for a chosen habit and date
    GET  /streaks/chart-data   JSON for Chart.js (7 or 30 days)

The heavy lifting (streaks, percentages, grid boxes, chart series) is done by
the functions in ``stats.py``.  This file only decides *which* habit to show,
checks the form input and returns the right page or JSON.

Notes on the rules
------------------
* A habit can only be completed once per day - enforced here with a friendly
  message and again by the UNIQUE constraint in the database.
* Future dates and dates before the habit started are refused.
* Only the logged-in user's habits can be selected; anything else is a 404.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

import stats
from models import Completion, Habit, db

streaks_bp = Blueprint("streaks", __name__)

# Only these two windows are offered by the chart dropdown.
ALLOWED_RANGES = (stats.WEEK_LENGTH, stats.GRID_LENGTH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def user_habits() -> list[Habit]:
    """Return the logged-in user's habits, alphabetically by name."""
    return (
        Habit.query.filter_by(user_id=current_user.id)
        .order_by(Habit.name)
        .all()
    )


def get_owned_habit(habit_id: int) -> Habit:
    """Return the habit if it belongs to the logged-in user, else 404."""
    habit = db.session.get(Habit, habit_id)
    if habit is None or habit.user_id != current_user.id:
        abort(404)
    return habit


def selected_habit(habits: list[Habit], habit_id: Optional[int]) -> Optional[Habit]:
    """Pick the habit for the page: the requested one, or the first one."""
    if not habits:
        return None
    for habit in habits:
        if habit.id == habit_id:
            return habit
    return habits[0]


# ---------------------------------------------------------------------------
# The streak page
# ---------------------------------------------------------------------------

@streaks_bp.get("/streaks")
@login_required
def streaks():
    """Render the streak page for one habit."""
    today = date.today()
    habits = user_habits()
    habit = selected_habit(habits, request.args.get("habit_id", type=int))

    if habit is None:
        # The template shows a friendly "add your first habit" state.
        return render_template("streaks.html", habits=[], selected=None)

    summary = stats.habit_summary(habit, today)
    boxes = stats.last_days(habit, stats.GRID_LENGTH, today)

    return render_template(
        "streaks.html",
        habits=habits,
        selected=habit,
        summary=summary,
        boxes=boxes,
        ranges=ALLOWED_RANGES,
    )


# ---------------------------------------------------------------------------
# Add a streak entry
# ---------------------------------------------------------------------------

@streaks_bp.post("/streaks/add")
@login_required
def add_streak():
    """Record a completion for a habit on a chosen day.

    The date defaults to today in the form.  Every rule has its own message
    so the user always knows what went wrong.
    """
    habit_id = request.form.get("habit_id", type=int)
    if habit_id is None:
        flash("Please choose a habit first.", "danger")
        return redirect(url_for("streaks.streaks"))

    habit = get_owned_habit(habit_id)
    raw_date = (request.form.get("entry_date") or "").strip()
    today = date.today()

    def back() -> str:
        """Redirect back to this habit's streak page."""
        return url_for("streaks.streaks", habit_id=habit.id)

    if not raw_date:
        flash("Please choose a date for the streak entry.", "danger")
        return redirect(back())

    try:
        day = date.fromisoformat(raw_date)
    except ValueError:
        flash("Please enter the date as YYYY-MM-DD.", "danger")
        return redirect(back())

    if day > today:
        flash("You cannot add a streak for a future date.", "danger")
        return redirect(back())

    if day < habit.created_at:
        flash(
            f"'{habit.name}' started on {habit.created_at:%d %b %Y}, "
            f"so {day:%d %b %Y} is before the habit existed.",
            "danger",
        )
        return redirect(back())

    if habit.is_completed_on(day):
        flash(
            f"'{habit.name}' is already complete for {day:%d %b %Y}.",
            "warning",
        )
        return redirect(back())

    db.session.add(Completion(habit_id=habit.id, completed_date=day))
    try:
        db.session.commit()
    except IntegrityError:
        # Safety net: the UNIQUE constraint caught a duplicate.
        db.session.rollback()
        flash("That day is already recorded for this habit.", "warning")
        return redirect(back())

    streak = stats.current_streak(habit, today)
    if streak >= habit.target_days:
        flash(
            f"🎉 {streak}-day streak for '{habit.name}' - "
            f"target of {habit.target_days} days reached!",
            "success",
        )
    else:
        flash(
            f"Streak added for {day:%d %b %Y}. "
            f"Current streak: {streak} day(s).",
            "success",
        )

    return redirect(back())


# ---------------------------------------------------------------------------
# Chart data
# ---------------------------------------------------------------------------

@streaks_bp.get("/streaks/chart-data")
@login_required
def chart_data():
    """Return the numbers for the two Chart.js graphs as JSON.

    Called by static/js/streaks.js whenever the habit or the 7/30-day
    dropdown changes, so the page does not have to reload.
    """
    habit_id = request.args.get("habit_id", type=int)
    if habit_id is None:
        return jsonify({"error": "habit_id is required"}), 400

    habit = get_owned_habit(habit_id)  # 404 for another user's habit

    days = request.args.get("days", default=stats.WEEK_LENGTH, type=int)
    if days not in ALLOWED_RANGES:
        days = stats.WEEK_LENGTH

    return jsonify(stats.chart_series(habit, days))
