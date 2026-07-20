# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A vibecoded prototype of an autonomous prior-authorization-prep agent for healthcare admin work. Takes a scheduled appointment requiring prior auth, runs it through extraction → policy-check → draft agents, then puts the result in front of a human for approval/edit/escalation before anything reaches a payer. Also handles the denial branch (resubmit vs. formal appeal). Part of a larger "autonomous administrative workforce" thesis — this is the first working slice.

Stack: Flask · PostgreSQL (Supabase recommended) · Anthropic Claude API · deployed on Render.

**Not HIPAA-compliant as-is.** Real login/CSRF exist, but no RBAC enforcement, no MFA, no BAAs executed. See `REAL_WORLD_DESIGN_PLAN.md` and `docs/compliance/` before this touches real patient data.

## Commands

```bash
# Setup
python -m venv venv
source venv/Scripts/activate        # Git Bash on Windows
pip install -r requirements.txt

# Schema (drops and recreates all tables — safe, synthetic data only)
python db/run_schema.py             # or: psql "$DATABASE_URL" -f db/schema.sql

# Seed synthetic demo data + 3 demo login accounts (staff1/supervisor1/admin1)
python db/seed.py

# Run dev server
flask --app app run --debug         # or via .claude/launch.json (venv/Scripts/python.exe app.py), port 5000

# Retention job — dry run by default, --days has no default on purpose
python db/retention_job.py --days 2555
python db/retention_job.py --days 2555 --confirm   # actually deletes
```

There is no test suite and no lint config in this repo currently.

`.env` needs `DATABASE_URL`, `ANTHROPIC_API_KEY`, `SECRET_KEY`; optional `ANTHROPIC_MODEL` (default `claude-sonnet-5`) and `ALLOW_DEMO_LOGIN` (default `false` — never `true` outside local dev, it's a full auth bypass, see risk #13 in `docs/compliance/hipaa_risk_assessment.md`).

## Architecture

**Case lifecycle (single source of truth: `cases.status`, enforced by a CHECK constraint in `db/schema.sql`):**
```
pending -> extracting -> policy_check -> draft_ready -> needs_review -> escalated
                                                              |
                                                          (human approves)
                                                              v
                                                          submitted -> approved
                                                              |            ^
                                                              v            |
                                                          denied -> resubmit_pending / appeal_pending -> closed
```
A case enters at `pending` via `routes/cases.py: new_case()` (optionally pre-filled from a `scheduled_appointments` row — a mock stand-in for a real EHR/scheduling hook, still Phase 3 of `REAL_WORLD_DESIGN_PLAN.md`). Editing a case (`edit_case()`) is only allowed while `status='pending'`, since extraction/policy-check/draft would reference stale data otherwise.

**Pipeline orchestration is plain Python, not LLM judgment.** `agents/pipeline.py: run_pipeline(case_id)` is the *only* place that calls the three agents in sequence and advances status. It is human-triggered (POST `/case/<id>/process`), never automatic on case creation. Any failure — missing chart note, malformed/empty agent JSON, no matching policy rows for the payer/category, a failed policy rule, or a raised exception — routes the case to `escalated` via a single `_escalate()` helper, never a silent failure or crash. `agents/policy_check_agent.py: any_rule_failed()` is the deterministic gate the pipeline trusts, not model confidence or free text.

**Three narrow agents, not one chained mega-prompt** (`agents/extraction_agent.py`, `policy_check_agent.py`, `draft_agent.py`), each independently testable:
- `extraction_agent.extract_fields()` — chart note text → structured fields, JSON array
- `policy_check_agent.check_policy()` — fields + payer's rules → pass/fail per rule
- `draft_agent.draft_submission()` — case summary + policy notes → submission narrative (always a proposal, never sent automatically)

All three call through `agents/claude_client.py: call_claude()`, a single shared client/call pattern, so model swaps, logging, or retries only need to change in one place. `parse_json_array()` there strips markdown code fences the model sometimes wraps JSON in (a real bug found when the pipeline was first wired up) and returns `None` on parse failure so callers route to escalation instead of crashing.

**Audit trail:** every agent action, human action, status change, and PHI read is logged to `case_events` (append-only, `event_type` CHECK-constrained). `case_detail()` in `routes/cases.py` logs a `phi_access` event on every view, not just writes — HIPAA audit requirements cover reads too. `actor` is always the real logged-in user (`current_user.actor`, e.g. `staff:jdoe`, via `models.py: User.actor`), never a placeholder, now that auth is wired up.

**DB access is a thin helper, not an ORM.** `db/connection.py: query(sql, params, fetch=True)` opens a connection, executes, optionally fetches as dicts (`RealDictCursor`), and closes — per-call, no pooling. Fine for prototype-level traffic; flagged in the code as needing a pooled connection before real production load. All routes and agents go through this one function.

**Routes** (`routes/cases.py`, `routes/auth.py`, both `@login_required` except `/login`) are intentionally thin — inline SQL via `query()`, no service/repository layer. `_resolve_choice()` in `routes/cases.py` handles server-side "select + Other free-text" resolution for payer/category/procedure/diagnosis dropdowns, no JS needed — consistent pattern used across the app instead of client-side validation.

**Auth**: Flask-Login sessions, `users.role` (staff/supervisor/admin) is captured in the schema and in `User.actor` but **nothing enforces a difference by role yet** — no RBAC gate exists on any route. Don't assume `role` does anything beyond labeling `actor` until that's actually built.

## Key files

- `agents/pipeline.py` — orchestration + escalation logic (read this first to understand the core flow)
- `agents/claude_client.py` — shared Claude call wrapper + fence-tolerant JSON parsing
- `routes/cases.py` — case intake, editing, pipeline trigger, review actions, denial/appeal branch
- `db/schema.sql` — canonical status/event-type enums live here as CHECK constraints, plus table comments explaining what's real vs. mock (`scheduled_appointments`)
- `CONTINUE.md` — running log of what's been built and what's next; check before starting new work
- `REAL_WORLD_DESIGN_PLAN.md` — the 6-phase path from this prototype to a compliant production system
- `docs/compliance/` — HIPAA risk assessment, PHI handling policy, BAA tracking, retention policy (explicitly drafts, not certified)
