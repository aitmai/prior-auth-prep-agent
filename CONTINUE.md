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
- Deployed: app on Render, database on Supabase — **not yet redeployed
  with today's changes**; Render's `DATABASE_URL` also needs the schema
  reset applied before the deployed app matches local.
- A `REAL_WORLD_DESIGN_PLAN.md` exists in this repo mapping the path from
  prototype to a real, compliant, production system

**Pipeline:** appointment scheduled -> case intake -> extraction agent ->
policy check agent -> draft agent -> human review (approve/escalate) ->
submitted -> payer decision -> approved or denied -> (if denied) resubmit
or formal appeal, each with its own status and audit trail.

**What I want to work on next:** [fill in — e.g. "build a case-intake route
so new cases can be created through the UI instead of only via seed.py,
and have it auto-trigger the pipeline" / "build the escalation queue screen
for supervisors" / "add authentication" / "start on Phase 1 of the
real-world design plan"]

Please pick up from here.
