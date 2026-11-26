"""
seed.py
=======
Fill the database with demo accounts and back-dated history so the finished
project can be demonstrated straight away (useful for the viva).

What it creates
---------------
Two users, so user isolation can be demonstrated:

    demo  / demo12345    demo@example.com
    alice / alice12345   alice@example.com

Four habits for ``demo`` with different patterns (a long run that already
reached its target, a habit with gaps, a brand-new habit and a lapsed one),
and two habits for ``alice``.

Run it with:

    python seed.py

WARNING: this DELETES the existing habits.db and rebuilds it, so it always
produces the same, predictable demo.  Do not run it on data you want to keep.
"""

from __future__ import annotations

from datetime import date, timedelta

from app import app
from models import Completion, Habit, User, db

DEMO_PASSWORD = "demo12345"
ALICE_PASSWORD = "alice12345"


def add_user(username: str, email: str, password: str) -> User:
    """Create a user with a hashed password and return it."""
    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # gives the user an id before habits reference it
    return user


def add_habit(
    owner: User,
    name: str,
    description: str,
    category: str,
    target_days: int,
    started_days_ago: int,
    completed_offsets: list[int],
) -> Habit:
    """Create a habit and its completions.

    ``completed_offsets`` counts *backwards* from today, so ``0`` is today,
    ``1`` is yesterday and so on.  Dates before the start date are skipped,
    which mirrors the rule the web form enforces.
    """
    today = date.today()
    habit = Habit(
        user_id=owner.id,
        name=name,
        description=description,
        category=category,
        target_days=target_days,
        created_at=today - timedelta(days=started_days_ago),
    )
    db.session.add(habit)
    db.session.flush()

    for offset in sorted(set(completed_offsets)):
        day = today - timedelta(days=offset)
        if habit.created_at <= day <= today:
            db.session.add(Completion(habit_id=habit.id, completed_date=day))

    return habit


def main() -> None:
    """Rebuild the database and insert the demo data."""
    with app.app_context():
        print("Rebuilding the database ...")
        db.drop_all()
        db.create_all()

        demo = add_user("demo", "demo@example.com", DEMO_PASSWORD)
        alice = add_user("alice", "alice@example.com", ALICE_PASSWORD)

        # 6-day run right now, a 12-day run earlier, plus scattered days.
        add_habit(
            demo, "Morning jog", "20 minutes around the park", "Fitness", 21, 34,
            list(range(0, 6)) + list(range(8, 20)) + [22, 23, 24, 25, 27, 28, 30, 31, 33],
        )

        # 11 consecutive days: this one already beat its 7-day target.
        add_habit(
            demo, "Read 20 pages", "Non-fiction before bed", "Learning", 7, 21,
            list(range(0, 11)) + [13, 14, 16, 18],
        )

        # Every other day: a low percentage to contrast with the others.
        add_habit(
            demo, "Drink 2L water", "Refill the bottle in the morning", "Health", 30, 14,
            [0, 2, 4, 6, 8, 10, 12],
        )

        # A habit the user stopped doing - current streak 0.
        add_habit(
            demo, "Meditate 10 minutes", "Quiet sit before breakfast", "Mindfulness", 21, 30,
            list(range(20, 30)),
        )

        # Alice's habits prove that each user only sees their own data.
        add_habit(
            alice, "Practice guitar", "15 minutes of scales", "Music", 14, 12,
            [0, 1, 2, 3, 5, 6, 8, 9, 10],
        )
        add_habit(
            alice, "Walk 8000 steps", "", "Fitness", 21, 9,
            [1, 2, 3, 4, 6, 7],
        )

        db.session.commit()

        # ---- summary ----
        print("\nDemo data created:\n")
        for user in (demo, alice):
            print(f"  {user.username} ({user.email})")
            for habit in user.habits.order_by(Habit.name):
                print(
                    f"    - {habit.name:<20} target {habit.target_days:>2} days, "
                    f"{habit.total_completions} completions"
                )
            print()

        print("Log in with:  demo / demo12345   (or alice / alice12345)")
        print("Start the app with:  python app.py")


if __name__ == "__main__":
    main()
