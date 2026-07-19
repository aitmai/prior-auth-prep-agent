# PHI handling policy (draft) — prior-auth-prep-agent

Status: **draft**, reflects current system behavior. Needs sign-off from
whoever owns compliance for the deploying organization before real patient
data touches this system. See `README.md` in this directory.

## What data the system handles

Per `db/schema.sql`, the `cases` table (and its linked tables) can hold:
patient name, age, diagnosis code (ICD-10), procedure code (CPT/HCPCS),
appointment date, free-text chart-note content, and free-text extracted
clinical fields. This is PHI under HIPAA when the data is real (the schema
header currently documents that only synthetic data is in scope today).

## What the extraction agent may pull

The extraction agent (`agents/extraction_agent.py`) is instructed to pull
only fields present in the chart note and to omit rather than guess. It has
no instruction limiting *which* categories of clinical detail it extracts —
today it will pull whatever the note contains. Before real chart notes are
fed to it, this policy needs an explicit allow-list (e.g. "diagnosis,
procedure, relevant treatment history, ordering physician" — not, say,
unrelated comorbidities or mental health/substance-use notes that carry
extra legal protection under 42 CFR Part 2) enforced in the system prompt
and spot-checked in the golden-set tests referenced in Phase 5 of
`REAL_WORLD_DESIGN_PLAN.md`.

## Retention

See `data_retention_policy.md`.

## Who can see PHI

Today: anyone who can reach the Flask app, since there is no
authentication (`CONTINUE.md` documents this gap explicitly). This must be
resolved — Phase 2 of the design plan — before this policy can claim any
real access control.

## Audit trail

`case_events` is append-only and now logs both actions (`human_action`,
`agent_action`, `status_change`) and reads (`phi_access`, added when a case
detail page is viewed — see `routes/cases.py: case_detail()`). Every
`phi_access` row currently records `actor = 'staff:unknown'` because there
is no real authentication yet to attribute the read to a specific person —
that limitation must be closed by Phase 2 for this audit trail to be
meaningful for a real HIPAA audit. The review-queue list view
(`GET /`) also displays PHI (patient name, service description) per row
and is **not** currently logged per-view; only individual case-detail
access is logged. This is a known gap, not an oversight — logging every
queue-list render was judged too noisy to be useful as designed; a future
pass could log it at a coarser grain (e.g. once per session) if a real
audit requirement calls for it.

## Vendors that will handle PHI

Supabase (database), Render (hosting), Anthropic (Claude API calls, which
receive chart-note text and extracted fields as part of the extraction and
draft prompts). See `baa_tracking.md`.
