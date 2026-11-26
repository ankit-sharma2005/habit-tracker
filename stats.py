"""
stats.py
========
Every calculation that the pages display: streaks, percentages, the 30-day
grid used by the streak page, the data for the Chart.js graphs and the
motivational message.

Why a separate module?
----------------------
Keeping the maths out of the routes means it can be tested on its own and
re-used by the dashboard *and* the streaks page.  No database queries are
written here - the functions only read a ``Habit`` object (and its
``completions`` relationship), so they are easy to reason about.

Every function that depends on "now" accepts an optional ``today`` date.
Passing a fixed date (e.g. ``date(2026, 1, 1)``) makes the result
predictable in tests instead of changing at midnight.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

WEEK_LENGTH = 7    # "weekly" statistics cover today and the 6 days before it
GRID_LENGTH = 30   # the streak page shows 30 boxes


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def start_date(habit) -> date:
    """Return the day the habit started (stored in ``created_at``)."""
    return habit.created_at


def completion_dates(habit) -> set[date]:
    """Return every day the habit was completed, as a set of dates."""
    return habit.completion_dates()


def eligible_days(start: date, today: date, window: Optional[int] = None) -> int:
    """Count the days a habit *could* have been completed.

    ``window=None`` means "since the habit started".
    ``window=7`` limits the count to the last 7 days.
    Days before the start date are never counted, and ``0`` is returned for a
    habit that starts in the future.
    """
    if start > today:
        return 0

    first = today - timedelta(days=window - 1) if window is not None else start
    first = max(first, start)  # never count days before the habit existed
    return (today - first).days + 1


def percentage(completed: int, possible: int) -> float:
    """Return ``completed / possible`` as a percentage rounded to 1 decimal.

    Guards against division by zero (a brand-new habit) and caps the result
    at 100 % in case more completions exist than possible days.
    """
    if possible <= 0:
        return 0.0
    return round(min(100.0, 100.0 * completed / possible), 1)


# ---------------------------------------------------------------------------
# Weekly numbers
# ---------------------------------------------------------------------------

def weekly_completions(habit, today: Optional[date] = None) -> int:
    """Return how many times the habit was completed in the last 7 days."""
    today = today or date.today()
    first = today - timedelta(days=WEEK_LENGTH - 1)
    return sum(1 for day in completion_dates(habit) if first <= day <= today)


def weekly_percentage(habit, today: Optional[date] = None) -> float:
    """Return the completion percentage for the last 7 days (0.0 - 100.0)."""
    today = today or date.today()
    done = weekly_completions(habit, today)
    possible = eligible_days(start_date(habit), today, WEEK_LENGTH)
    return percentage(done, possible)


def overall_percentage(habit, today: Optional[date] = None) -> float:
    """Return the completion percentage since the habit started."""
    today = today or date.today()
    done = len(completion_dates(habit))
    possible = eligible_days(start_date(habit), today)
    return percentage(done, possible)


# ---------------------------------------------------------------------------
# Streaks
# ---------------------------------------------------------------------------

def streak_runs(habit) -> list[list[date]]:
    """Split the completed dates into consecutive runs.

    Example: dates 1, 2, 3, 7, 8 become ``[[1, 2, 3], [7, 8]]``.
    A "run" is what most people call a streak; keeping the individual days
    lets us colour the ticks of a *completed* target run differently.
    """
    dates = sorted(completion_dates(habit))
    runs: list[list[date]] = []

    for day in dates:
        if runs and (day - runs[-1][-1]).days == 1:
            runs[-1].append(day)  # continues the previous day: extend the run
        else:
            runs.append([day])    # first day, or a gap: start a new run

    return runs


def current_streak(habit, today: Optional[date] = None) -> int:
    """Return the number of consecutive completed days up to today.

    If today is not completed yet the count starts at yesterday, because a
    streak is only broken once the day is actually over.
    """
    today = today or date.today()
    dates = completion_dates(habit)

    cursor = today if today in dates else today - timedelta(days=1)

    streak = 0
    while cursor >= start_date(habit) and cursor in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_streak(habit) -> int:
    """Return the longest run of consecutive completed days, ever."""
    return max((len(run) for run in streak_runs(habit)), default=0)


def completed_run_dates(habit) -> set[date]:
    """Return the days that belong to a run which reached ``target_days``.

    The streak page uses this to draw those ticks in a different colour and
    to decide whether the "🎉 target completed" badge should appear.
    """
    target = max(1, int(habit.target_days or 1))
    return {
        day
        for run in streak_runs(habit)
        if len(run) >= target
        for day in run
    }


# ---------------------------------------------------------------------------
# Motivation
# ---------------------------------------------------------------------------

def motivational_message(weekly_percent: float, current: int, weekly_count: int) -> str:
    """Return a short encouragement based on recent performance.

    The checks run from best to worst and only the first match is used, so
    a perfect week is praised ahead of a long streak.
    """
    if weekly_count >= WEEK_LENGTH and weekly_percent >= 100.0:
        return "Perfect week - every single day completed. Outstanding!"
    if current >= 7:
        return f"{current}-day streak, keep going!"
    if current >= 3:
        return f"{current} days in a row - the habit is forming."
    if current == 2:
        return "Two days in a row. One more makes it three!"
    if current == 1:
        return "You showed up today. Come back tomorrow to make it two."
    if weekly_count == 0:
        return "Nothing logged this week yet. One completion starts the momentum."
    return "Good progress this week - a few more days will lock it in."


# ---------------------------------------------------------------------------
# One dictionary per habit, used by the dashboard and the streak page
# ---------------------------------------------------------------------------

def habit_summary(habit, today: Optional[date] = None) -> dict:
    """Collect every number for one habit into a plain dictionary.

    Templates can then read ``card.name``, ``card.weekly_percent`` and so on
    without running any queries themselves.
    """
    today = today or date.today()

    weekly_count = weekly_completions(habit, today)
    weekly_pct = weekly_percentage(habit, today)
    streak = current_streak(habit, today)
    target = max(1, int(habit.target_days or 1))

    return {
        "id": habit.id,
        "name": habit.name,
        "description": habit.description,
        "category": habit.category,
        "target_days": target,
        "start_date": start_date(habit),
        "done_today": habit.is_completed_on(today),
        "weekly_count": weekly_count,
        "weekly_possible": eligible_days(start_date(habit), today, WEEK_LENGTH),
        "weekly_percent": weekly_pct,
        "overall_percent": overall_percentage(habit, today),
        "current_streak": streak,
        "longest_streak": longest_streak(habit),
        "total_completions": len(completion_dates(habit)),
        "target_progress": min(100.0, round(100.0 * streak / target, 1)),
        "target_reached": longest_streak(habit) >= target,
        "message": motivational_message(weekly_pct, streak, weekly_count),
    }


# ---------------------------------------------------------------------------
# The 30-day grid shown on the streak page
# ---------------------------------------------------------------------------

def last_days(habit, days: int = GRID_LENGTH, today: Optional[date] = None) -> list[dict]:
    """Return one dictionary per day for the streak grid.

    Statuses:
    * ``done``    - completed that day (green tick),
    * ``missed``  - the habit existed but was not completed (red cross),
    * ``before``  - the habit had not started yet (empty box).

    ``highlight`` is True for days inside a run that reached the target, so
    the template can colour those ticks differently.
    """
    today = today or date.today()
    dates = completion_dates(habit)
    highlighted = completed_run_dates(habit)
    start = start_date(habit)

    boxes: list[dict] = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)

        if day < start:
            status = "before"
        elif day in dates:
            status = "done"
        else:
            status = "missed"

        boxes.append(
            {
                "date": day,
                "status": status,
                "highlight": day in highlighted,
                "is_today": day == today,
                "weekday": day.strftime("%a"),
            }
        )

    return boxes


# ---------------------------------------------------------------------------
# Data for the Chart.js graphs
# ---------------------------------------------------------------------------

def chart_series(habit, days: int = WEEK_LENGTH, today: Optional[date] = None) -> dict:
    """Return the numbers the two charts need, as JSON-friendly data.

    * ``labels``     - one label per day, oldest first,
    * ``completed``  - 1 when the habit was done that day, otherwise 0,
    * ``cumulative`` - running total of completions inside the window,
    * ``doughnut``   - overall completed vs missed days and the percentage.
    """
    today = today or date.today()
    days = GRID_LENGTH if int(days) >= GRID_LENGTH else WEEK_LENGTH
    dates = completion_dates(habit)

    labels: list[str] = []
    completed: list[int] = []
    cumulative: list[int] = []
    running = 0

    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        done = 1 if day in dates else 0
        running += done

        # Short labels keep the axis readable on a phone.
        labels.append(day.strftime("%d %b"))
        completed.append(done)
        cumulative.append(running)

    possible = eligible_days(start_date(habit), today)
    done_total = len(dates)

    return {
        "habit": {
            "id": habit.id,
            "name": habit.name,
            "target_days": habit.target_days,
        },
        "days": days,
        "labels": labels,
        "completed": completed,
        "cumulative": cumulative,
        "doughnut": {
            "completed": done_total,
            "missed": max(0, possible - done_total),
            "possible": possible,
            "percent": overall_percentage(habit, today),
        },
    }
