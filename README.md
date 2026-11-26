# Habit Tracker — Flask web application

A final-year project: record daily habits, mark them complete, and watch the
streaks grow. Each person has their own account and only ever sees their own
habits and history.

**Stack:** Python 3 + Flask · SQLite (Flask-SQLAlchemy) · Bootstrap 5 ·
Chart.js · Flask-Login · werkzeug.security

## Folder structure

```
habit_tracker_web/
├── app.py                  # creates the Flask app, connects db + login manager
├── models.py               # User, Habit, Completion (SQLAlchemy models)
├── auth.py                 # register / login / logout blueprint
├── habits.py               # dashboard + add / edit / delete / complete
├── streaks.py              # streak page, add-streak form, chart JSON
├── stats.py                # streaks, percentages, grid, chart data (pure maths)
├── seed.py                 # demo users, habits and back-dated history
├── requirements.txt
├── habits.db               # created automatically on first run
├── templates/
│   ├── base.html           # navbar, flash messages, footer
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── habit_form.html     # shared add/edit form
│   ├── streaks.html        # the main feature page
│   └── 404.html
└── static/
    ├── css/style.css
    ├── js/main.js          # delete confirmation + auto-dismiss flashes
    ├── js/streaks.js       # Chart.js bar/line + doughnut
    └── vendor/             # Bootstrap 5.3.3 and Chart.js 4.4.3 (local copies)
```

Bootstrap and Chart.js are copied into `static/vendor/`, so the app also works
without an internet connection — handy for a live demo.

## Setup and run

```bash
cd habit_tracker_web

# 1. create a virtual environment
python -m venv .venv

# 2. activate it
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # macOS / Linux

# 3. install the dependencies
pip install -r requirements.txt

# 4. (optional but recommended for the demo) load sample data
python seed.py

# 5. start the app
python app.py                   # http://127.0.0.1:5000
```

Then open <http://127.0.0.1:5000> and log in with:

| Username | Password | What to look at |
| --- | --- | --- |
| `demo` | `demo12345` | four habits with different streak patterns |
| `alice` | `alice12345` | different habits — proves users are isolated |

`python seed.py` **deletes and rebuilds** `habits.db`, so it always produces the
same demo. Register your own account instead if you want to keep data.

Set `SECRET_KEY` in the environment before deploying anywhere real; the default
value in `app.py` is for local development only.

## Pages

| Route | Page | What it does |
| --- | --- | --- |
| `/register` | Register | username, email, password + confirmation, with clear errors |
| `/login` | Log in | username **or** email plus password |
| `/dashboard` | Dashboard | all habits, today's status, weekly progress, complete/edit/delete |
| `/habits/new` | Add habit | name, description, category, start date, target streak |
| `/habits/<id>/edit` | Edit habit | same form, pre-filled |
| `/streaks` | Streaks | habit dropdown, add-streak form, 30-day grid, charts |
| `/streaks/chart-data` | JSON | data for Chart.js (7 or 30 days) |

## Rules the app enforces

- A habit can be completed **once per day** — checked in the route *and* by
  `UNIQUE(habit_id, completed_date)` in the database.
- **No future dates**, and no dates before the habit's start date.
- Passwords are stored only as `werkzeug.security` hashes.
- Every habit/streak route requires a login, and every query is filtered by
  `user_id`. Asking for another user's habit returns 404, not their data.
- Deleting a habit deletes its completion history (cascade).

## How the numbers are calculated

| Statistic | Formula |
| --- | --- |
| 7-day count | completions between today-6 and today |
| Weekly % | completions in that window ÷ days the habit existed in the window |
| Overall % | all completions ÷ all days since the start date |
| Current streak | consecutive completed days counted back from today (yesterday if today is not ticked yet) |
| Longest streak | longest run of consecutive completed dates |
| Target reached | longest run ≥ `target_days` → 🎉 badge and gold ticks |

## Notes / possible improvements

- Add CSRF protection with Flask-WTF (`FlaskForm`) before any public deploy.
- Reminder emails or browser notifications.
- CSV / PDF export of the history.
- Dark mode toggle (Bootstrap 5.3 supports `data-bs-theme`).
- Password reset by email, and account deletion.
- Move from SQLite to PostgreSQL for multiple simultaneous writers.
