# 🩺 Prior Auth Prep Agent

Vibecoded prototype of an autonomous prior-authorization-prep agent, built under human supervision at every step. Part of the healthcare admin-workforce AI thesis.

[![aitmai](https://img.shields.io/badge/built%20by-aitmai-blue)](https://github.com/aitmai)

## What it does

Takes a scheduled appointment that requires prior authorization, runs it through extraction, policy-check, and drafting agents, and puts the result in front of a human for approval, edit, or escalation before anything is submitted to a payer. Also handles the denial branch — resubmit vs. formal appeal vs. peer-to-peer review.

## Features

- Three narrow, independently-testable Claude agents (extraction, policy check, draft) — not one chained mega-prompt
- Deterministic escalation logic: any failed policy rule or missing field routes to a human, by code, not by model judgment
- Full audit trail (`case_events`) for every agent and human action
- Denial/appeal branch with deadline tracking
- ROI dashboard fields (`metrics_snapshot`) baselined against published manual prior-auth time/cost figures

## Stack

Flask · PostgreSQL · Anthropic Claude API · Render

## Setup

1. Clone the repo and `cd` into it.
2. Create a virtualenv and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in `DATABASE_URL` and `ANTHROPIC_API_KEY` (see "Setting up DATABASE_URL" below if you don't have a Postgres instance yet).
4. Create the schema (either method works — same target database):
   ```
   psql "$DATABASE_URL" -f db/schema.sql
   ```
   or, without needing the psql CLI installed:
   ```
   python db/run_schema.py
   ```
5. Load synthetic demo data:
   ```
   python db/seed.py
   ```
6. Run the app:
   ```
   flask --app app run --debug
   ```
7. Visit `http://localhost:5000` for the review queue.

## Setting up DATABASE_URL

**Option A — Supabase (recommended, free tier is persistent — no 30-day expiration):**

1. Go to [supabase.com](https://supabase.com) and sign in or create an account.
2. **New project** → name it (e.g. `prior-auth-prep`), set a database password (save it — you'll need it in the connection string), pick a region, click **Create new project**. Takes about 2 minutes to provision.
3. Once ready, go to **Project Settings** (gear icon) → **Database** → **Connection string** → select the **URI** tab.
4. Copy the string — it looks like `postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxx.supabase.co:5432/postgres`.
5. Replace `[YOUR-PASSWORD]` with the password you set in step 2.
6. Paste it into `.env` as `DATABASE_URL=...`.
7. Run the schema and seed as in steps 4–5 above (`python db/run_schema.py` then `python db/seed.py`) — or, just as easily, open Supabase's **SQL Editor** in the dashboard, paste the contents of `db/schema.sql`, and click **Run**. Same for `db/seed.py`'s SQL if you'd rather not run Python locally — though the seed script has to run as Python since it generates UUIDs and dates in code.
8. When deploying the Flask app itself (Render, or wherever), add the same `DATABASE_URL` as an environment variable in that service's settings — never commit it to the repo.

**Option B — local Postgres via Docker (for local testing only):**

```
docker run --name pa-prep-db -e POSTGRES_PASSWORD=devpass -p 5432:5432 -d postgres
```

Then set:
```
DATABASE_URL=postgresql://postgres:devpass@localhost:5432/postgres
```

Either option, the schema and seed steps (steps 4–5 above) are identical. Avoid Render's free Postgres tier for this project — it auto-expires after 30 days.

## Environment variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `ANTHROPIC_API_KEY` | Claude API key |
| `ANTHROPIC_MODEL` | Optional, defaults to `claude-sonnet-5` |
| `SECRET_KEY` | Flask session secret |

## Deploying to Render

Push to `github.com/aitmai/prior-auth-prep-agent`, connect the repo in Render as a web service, set the environment variables above (with `DATABASE_URL` pointing at your Supabase instance, not Render Postgres) in the Render dashboard, and set the start command to `gunicorn app:app`.

## Security note

All patient data in `db/seed.py` is synthetic. This prototype has no authentication layer and is not HIPAA-compliant as-is — do not point it at real patient data without adding access controls, encryption at rest/in transit, and a BAA-covered hosting environment.

## Troubleshooting

**`bash: .../python: No such file or directory` when running any `python` command:**
Your shell likely still has a different project's virtualenv activated (e.g. quant-fund-system's `.venv`), even if the prompt shows `(.venv)` — that's a stale/cached path, not this project's environment. Fix:
```
deactivate
cd /path/to/prior-auth-prep-agent
python -m venv venv
source venv/Scripts/activate   # Git Bash on Windows
which python                   # should point inside this project's venv/
hash -r                        # if which python still looks wrong
pip install -r requirements.txt
```

## License

MIT © 2026 aitmai
