# Continuing prior-auth-prep-agent

Paste the block below into a new chat to resume with full context.

---

I'm continuing work on **prior-auth-prep-agent** — a vibecoded prototype of an
autonomous prior-authorization-prep agent, the first working slice of a
broader "autonomous administrative workforce" healthcare AI thesis.

**Stack:** Flask + PostgreSQL (Supabase) + Anthropic Claude API (Sonnet 5),
deployed on Render.

**Built so far:**
- Full DB schema: `cases`, `case_events`, `extracted_fields`, `policies`,
  `policy_check_results`, `drafts`, `denials`, `metrics_snapshot`. `cases`
  now also has `chart_note_text` (raw intake note) and `service_category`
  (matches `policies.service_category`).
- Three narrow Claude agent functions — extraction, policy check, draft —
  kept separate rather than chained into one prompt. **Now actually wired
  into a pipeline** (`agents/pipeline.py: run_pipeline(case_id)`), triggered
  by a "Run intake pipeline" button on a `pending` case's detail page (POST
  `/case/<id>/process`). Deterministic escalation on any failure — empty/
  malformed agent output, no matching policy for the payer/category, a
  failed policy rule, or an API exception — all route to `escalated`, never
  a silent failure or a crash.
- Fixed a real bug surfaced by wiring the agents up for the first time: the
  model wraps JSON output in ` ```json ` fences despite being told not to,
  which silently broke `json.loads` in both `extraction_agent.py` and
  `policy_check_agent.py`. Added `agents/claude_client.py: parse_json_array()`,
  a shared fence-tolerant parser, used by both.
- Bumped `anthropic` 0.34.2 -> 0.117.0 (pinned in `requirements.txt`) — the
  old version was incompatible with the installed `httpx` and crashed the
  app on startup (`Client.__init__() got an unexpected keyword argument
  'proxies'`). Pre-existing bug, unrelated to the pipeline work, but it
  blocked testing so it got fixed here too.
- Deterministic escalation logic in plain Python, not LLM judgment
- Flask routes for the review queue, case detail, and
  process / approve / escalate / resubmit / appeal actions
- Dark navy-themed GUI: queue dashboard with status columns + ROI metrics,
  case detail page with an intake-note card, service category, and a
  denial-handling section
- Seed data: 6 synthetic cases. The 2 `pending` cases (R. Kim, J. Patel)
  now carry real chart-note text and run cleanly through the full pipeline
  end-to-end (extraction -> policy check -> draft -> needs_review) —
  verified live in the browser, not just read through.
- `schema.sql` now drops and recreates all tables (safe — synthetic data
  only) so `python db/run_schema.py && python db/seed.py` is a clean reset
  during iteration.
- `.claude/launch.json` added so the Flask dev server can be started via
  the standard `run`/preview tooling (`venv/Scripts/python.exe app.py`,
  port 5000).
- **Case intake route** — `GET/POST /case/new` (now `case_form.html`,
  see below) creates a real `pending` case (patient info, payer, service
  category, chart note) through the UI instead of only via `db/seed.py`.
  Linked from the queue via "+ New case". Stays manually triggered into
  the pipeline (no auto-run on creation), matching the "nothing proceeds
  without a human action" pattern used everywhere else.
- **Editable drafts** — the draft textarea on `case_detail.html` is now
  editable while a case is `draft_ready`/`needs_review`, saved via
  `POST /case/<id>/draft/edit` as a new `drafts` version (`edited_by` set).
  Becomes read-only once submitted, since at that point it's a record of
  what was actually sent, not something to revise.
- **Closed the loop on payer decisions** — two new routes:
  `POST /case/<id>/decision` (on a `submitted` case: approved -> `approved`;
  denied -> `denied` + creates the `denials` row with reason/appeal
  deadline) and `POST /case/<id>/denial/resolve` (on a case marked for
  resubmit/appeal: records `overturned`/`upheld`, sets `denials.resolved_at`
  + `outcome`, moves the case to `approved` or `closed`). Previously
  `resubmit`/`appeal` set a path but nothing ever closed the loop.
- **Phase 1 compliance — started, not finished:**
  - Code: `case_events` now has a `phi_access` event type, logged on every
    `case_detail` view (not just writes) — verified writing real rows.
    `actor` is still `'staff:unknown'` on every one of these until Phase 2
    auth exists, which limits how useful this audit trail is for now.
  - Code: `db/retention_job.py` — a dry-run-by-default script that deletes
    cases (cascading to all child tables) past a retention window; `--days`
    has no default on purpose, so the actual number has to come from a
    real compliance decision, not a guess. Not yet wired into a schedule.
  - Docs (drafts, not final): `docs/compliance/phi_handling_policy.md`,
    `hipaa_risk_assessment.md` (12 identified risks, explicitly not a
    certified assessment), `baa_tracking.md` (checklist only — no BAA has
    actually been executed with Supabase/Render/Anthropic; that needs the
    practice's own outreach), `data_retention_policy.md`. See
    `docs/compliance/README.md` for what's real vs. draft here.
- **Case intake now has a scheduling picker + editing** — a
  `scheduled_appointments` table (`db/schema.sql`) is a MOCK stand-in for a
  real EHR/scheduling hook (that's still Phase 3 — this doesn't integrate
  with anything real). `/case/new` shows unused mock appointments as
  clickable cards; picking one pre-fills the form via
  `?from_appointment=<id>` and marks it `used_at` on case creation. Seeded
  4 mock appointments in `db/seed.py`. New `GET/POST /case/<id>/edit`
  route lets you correct a case's fields — **only while `status='pending'`**
  (blocked with a flash message otherwise, since extraction/policy
  check/draft would reference stale data once the pipeline has run).
- **Procedure code, diagnosis code, payer, and service category are now
  dropdowns**, not free text — `templates/case_form.html` (replaces the
  old `case_new.html`, now shared between new-case and edit-case). Payer
  and category are backed by real distinct values from `policies`;
  procedure/diagnosis codes are a curated list of the codes already used
  in this app's seed data (real CPT/ICD-10 code sets have tens of
  thousands of entries — nothing here has that reference data loaded).
  Every dropdown has an "Other (type below)" option with a free-text
  fallback, resolved server-side in `routes/cases.py: _resolve_choice()`
  — no JS needed, consistent with the rest of the app.
- **Queue view now shows every actionable status** — `queue.html` had only
  4 columns (pending, needs_review, escalated, submitted); added `denied`,
  `resubmit_pending`, `appeal_pending` so those cases don't vanish from
  view. `approved`/`closed` stay excluded on purpose — genuinely terminal,
  no action needed.
- **Real authentication landed (Phase 2, partially)** — `users` table
  (username/password_hash/role), Flask-Login for sessions, `routes/auth.py`
  (`/login`, `/logout`), every case route now requires `@login_required`.
  Every `actor` written to `case_events` (including `phi_access` reads) now
  comes from the real logged-in session (`current_user.actor`, e.g.
  `staff:staff1`) instead of an unverified form field or `'staff:unknown'`
  — verified live: logged in, escalated a case, confirmed the audit row
  said `staff:staff1`, logged out, confirmed the queue was inaccessible
  again. Also added Flask-WTF CSRF protection app-wide while touching every
  form anyway, since the risk assessment flagged CSRF as worse once real
  sessions exist. Closed a small pre-existing gap found along the way:
  `resubmit`/`file_appeal` never logged a `case_events` row at all before
  today. 3 demo accounts seeded in `db/seed.py`
  (`staff1`/`supervisor1`/`admin1`, throwaway passwords, documented as
  demo-only, never to reach a real deployment). Updated
  `hipaa_risk_assessment.md` and `phi_handling_policy.md` to reflect this.
  **Not done:** `users.role` is captured but nothing enforces a difference
  by role yet — no admin/supervisor-only action exists to gate. That's
  Phase 2's RBAC bullet, still open.
- **"Test without login" button** — `POST /login/demo` (`routes/auth.py`)
  logs straight in as the `staff1` demo account, no password. Gated behind
  `ALLOW_DEMO_LOGIN` (`app.py`), which defaults to `false`/unset
  (`.env.example`) and is only `true` in the local `.env`. Verified live
  both ways: button + route work when the flag is on, and — with the flag
  off — the button disappears *and* a direct POST to `/login/demo` still
  gets rejected (checked via fetch, not just hiding the UI element).
  Tracked as risk #13 in `hipaa_risk_assessment.md`: this is a full auth
  bypass if the flag is ever set `true` anywhere real PHI is reachable;
  recommend removing the route entirely before any real deployment rather
  than trusting the flag alone.
- Deployed: app on Render, database on Supabase — **not yet redeployed
  with any of today's changes**; Render's `DATABASE_URL` also needs the
  schema reset applied before the deployed app matches local. Also note:
  deploying auth means setting real values for `SECRET_KEY`, replacing the
  demo user passwords, and making sure `ALLOW_DEMO_LOGIN` is never set on
  Render — before this is anything but a local prototype.
- A `REAL_WORLD_DESIGN_PLAN.md` exists in this repo mapping the path from
  prototype to a real, compliant, production system

**Pipeline:** appointment scheduled (mock picker today, real EHR/scheduling
hook in Phase 3) -> case intake (create or edit while pending) ->
extraction agent -> policy check agent -> draft agent -> human review
(approve/edit/escalate) -> submitted -> payer decision -> approved or
denied -> (if denied) resubmit or formal appeal -> resolution
(overturned/upheld), each with its own status and audit trail, all behind
a real login now. This is a fully closed loop end to end, verified live in
the browser at every step.

**What I want to work on next:** [fill in — e.g. "enforce RBAC — restrict
some action to supervisor/admin roles now that users.role actually exists"
/ "deploy today's changes to Render + reset the Supabase schema, including
real SECRET_KEY and non-demo user passwords" / "keep going on Phase 1 —
get the BAAs actually signed, get the risk assessment reviewed by someone
qualified" / "let staff schedule a new mock appointment through the UI
instead of only via seed.py" / "build the escalation queue screen for
supervisors"]

Please pick up from here.
