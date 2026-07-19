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

Real login now exists (`routes/auth.py`, Flask-Login) and every case route
requires `@login_required` — anonymous access is blocked. There is no
role-based restriction yet: any logged-in account (`staff`, `supervisor`,
or `admin`) can see and act on every case identically, since no route
currently differentiates by role. The 3 seeded accounts
(`db/seed.py`) use throwaway demo passwords and must never be reused in a
real deployment — real user provisioning (real people, real passwords, a
real password policy, ideally MFA) is still outstanding.

## Audit trail

`case_events` is append-only and logs actions (`human_action`,
`agent_action`, `status_change`) and reads (`phi_access`, logged when a
case detail page is viewed — see `routes/cases.py: case_detail()`). Every
event's `actor` now comes from the logged-in session
(`current_user.actor`, e.g. `staff:staff1`) rather than an unverified form
field or a placeholder — this is real progress, but it's only as
trustworthy as the login itself (see the demo-password caveat above). The
review-queue list view (`GET /`) also displays PHI (patient name, service
description) per row and is **not** currently logged per-view; only
individual case-detail access is logged. This is a known gap, not an
oversight — logging every queue-list render was judged too noisy to be
useful as designed; a future pass could log it at a coarser grain (e.g.
once per session) if a real audit requirement calls for it.

## Vendors that will handle PHI

Supabase (database), Render (hosting), Anthropic (Claude API calls, which
receive chart-note text and extracted fields as part of the extraction and
draft prompts). See `baa_tracking.md`.
