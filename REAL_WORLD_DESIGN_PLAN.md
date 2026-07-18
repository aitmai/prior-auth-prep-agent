# Real-world design plan — prior-auth-prep-agent

This prototype proves the pipeline and the UI. Turning it into something a
real practice could actually run on requires six areas of work, roughly in
this order — each phase assumes the previous one is done, but Phase 1
(compliance) has to be settled before any real patient data touches this
system, full stop.

## Phase 1 — Compliance foundation (do this before anything else)

- **BAA (Business Associate Agreement)** with every vendor in the stack
  that will touch real PHI: Supabase, Render, Anthropic. Confirm each
  offers a BAA on your plan tier — some require an enterprise/paid tier.
- **HIPAA risk assessment** — formal, documented, covering this
  application specifically (not a generic org-wide assessment).
- **PHI handling policy** — written policy on what data the extraction
  agent is allowed to pull, how long it's retained, who can see it.
- **Audit logging expansion** — `case_events` already logs actions;
  extend it to log every read of PHI, not just writes, since HIPAA audit
  requirements cover access, not just modification.
- **Data retention & deletion policy** — define how long denied/closed
  cases are kept, and build the actual deletion job, not just a policy
  doc.

## Phase 2 — Security & access control

- **Authentication** — real login (Flask-Login, or an identity provider
  like Auth0/Cognito/Okta) replacing the current `actor` form field, which
  is just a free-text placeholder right now.
- **Role-based access** — at minimum: staff (can approve/escalate/resubmit),
  supervisor (can also see escalated queue, override), admin (can edit
  payer policy rules). The current schema has no user/role tables yet.
- **Encryption** — confirm TLS in transit (Render/Supabase default to
  this, but verify) and encryption at rest (Supabase Postgres supports
  this; confirm it's enabled, not just available).
- **Secrets management** — move off `.env` files for production; use
  Render's environment variable encryption or a dedicated secrets manager.
- **Session security** — real `SECRET_KEY` rotation policy, session
  timeout, CSRF protection on the action forms (Flask-WTF adds this
  cheaply).

## Phase 3 — Real data integration

This is the biggest lift. Right now `extracted_fields` and `drafts` are
seeded by hand; a real system needs:

- **EHR integration** — pull chart data via FHIR API (Epic, Cerner, or
  whatever EHR the target practice uses). Start against a FHIR sandbox
  (Epic's is free to register for) before touching a real instance.
- **Payer connectivity** — actual submission needs either a clearinghouse
  relationship or direct FHIR-based ePA per CMS-0057-F. This is a real
  integration project per payer, not a generic API — budget for it
  per-payer, starting with whichever payer the pilot practice uses most.
- **Scheduling system hook** — the case-intake trigger ("appointment
  scheduled for a PA-requiring service") needs to come from wherever the
  practice actually schedules appointments, not a manual seed script.

## Phase 4 — Reliability & operations

- **Background job queue** — Claude API calls currently run synchronously
  in the request. Move extraction/policy-check/draft to a queue (Celery,
  RQ, or Render's background workers) so a slow LLM call doesn't hang a
  staff member's browser tab.
- **Retry logic & rate limiting** — the agent functions currently have no
  retry on a failed/malformed Claude response beyond returning an empty
  list; that should route to escalation with a clear "agent failed" reason,
  and API rate limits need backoff handling.
- **Connection pooling** — `db/connection.py`'s open/close-per-query
  pattern won't hold up under real concurrent staff traffic; move to
  SQLAlchemy with a connection pool or `psycopg2.pool`.
- **Monitoring & alerting** — error tracking (Sentry or similar), and
  alerting specifically on the escalation rate and average turnaround
  metrics, since a spike in either is the earliest sign something's wrong.

## Phase 5 — Testing & clinical validation

- **Golden-set testing** — build a set of real (de-identified) or
  realistic synthetic cases with known-correct outcomes, and test each
  agent against it before every deploy, not just ad hoc.
- **Clinical review** — a nurse, coder, or physician should review a
  sample of draft-agent outputs before this touches real submissions.
  This isn't optional — it's the equivalent of the "human review" step
  in the pipeline, applied to the pipeline itself before it ships.
- **Failure-mode review** — deliberately test what happens on malformed
  chart data, missing fields, and payer policies with no matching rule,
  and confirm every one of those routes to escalation rather than silently
  proceeding.

## Phase 6 — Pilot & rollout

- **Shadow mode first** — run the system alongside the existing manual
  process for a set period without it being the system of record; compare
  its extraction/policy-check output against what staff actually did.
- **Success metrics tied to the ROI baseline** — track avg minutes/case
  and escalation rate against the CAQH/AMA manual baseline used in this
  project's original numbers ($3.41–$10.97/request, 16–24 min manual) to
  get a real, defensible before/after comparison.
- **Gradual rollout** — one payer, one service category first (e.g. just
  biologic infusions through one payer), before expanding scope.
- **Feedback loop** — a way for staff to flag a bad agent output that
  feeds back into the golden-set tests, not just a one-off correction.

## What doesn't change

The core architectural decisions from the prototype hold up at
production scale and don't need rework: separate, narrow agent functions
per step; deterministic (non-LLM) escalation logic; append-only audit
trail; nothing auto-submits without a human action. Those are the parts
of this thesis that were right from the start — the work above is about
making the data real and the system trustworthy at scale, not about
redesigning the pipeline itself.
