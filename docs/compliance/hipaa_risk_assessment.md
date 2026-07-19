# HIPAA risk assessment — starting point (draft)

Status: **not a certified HIPAA Security Risk Assessment.** This is a
structured first pass over this specific application's architecture and
data flows, meant to give whoever conducts the real assessment (internal
compliance staff, outside counsel, or a qualified HIPAA compliance
consultant) a head start, not to replace them. See `README.md` in this
directory. Every "Mitigation status" below is a statement about the code
as of this writing, not a claim that the risk is closed.

## Scope

The Flask application, its Postgres database (Supabase), its hosting
(Render), and its use of the Anthropic Claude API, as they exist in this
repository. Does not cover the deploying organization's broader network,
endpoint security, physical office security, or staff training — those
are real inputs a full assessment needs that are outside this codebase's
visibility.

## Identified risks

| # | Risk | Where | Likelihood/impact if unaddressed | Mitigation status |
|---|------|-------|-----------------------------------|--------------------|
| 1 | No authentication — anyone who can reach the app can view/edit all PHI | Whole app; `CONTINUE.md` documents this gap | High/High | Not mitigated. Phase 2 of `REAL_WORLD_DESIGN_PLAN.md`. |
| 2 | No role-based access control — no distinction between staff/supervisor/admin | Whole app | High/Medium | Not mitigated. Phase 2. |
| 3 | Secrets (`DATABASE_URL`, `ANTHROPIC_API_KEY`) currently loaded from `.env` | `app.py`, all `db`/`agents` modules | Medium/High if `.env` is ever committed or the host is compromised | Partially mitigated — `.env` is expected to be gitignored (verify) and not used in production hosting, which should use Render's encrypted env vars instead. |
| 4 | PHI sent to a third-party LLM (Anthropic) as part of every agent call | `agents/extraction_agent.py`, `policy_check_agent.py`, `draft_agent.py` | High impact if no BAA/data-handling terms in place | Not mitigated — no BAA executed yet; see `baa_tracking.md`. |
| 5 | No encryption-at-rest confirmation for the database | Supabase Postgres | Medium/High | Unverified — Supabase supports it; needs an explicit confirmation, not an assumption. |
| 6 | TLS in transit | Render/Supabase connections | Low if defaults hold | Likely covered by platform defaults; verify, don't assume. |
| 7 | No session security / CSRF protection on state-changing forms (approve, escalate, decision, etc.) | `routes/cases.py` — all POST routes | Medium (worse once real auth exists, since CSRF becomes a way to act *as* an authenticated user) | Not mitigated. Phase 2 explicitly calls for Flask-WTF or equivalent. |
| 8 | Audit trail (`case_events`) cannot attribute reads or writes to a real person | Every route — `actor` is a free-text field with no verification | High for HIPAA's access-audit requirement, which expects accountable identity | Not mitigated until Phase 2 auth lands; `phi_access` logging (added this session) records *that* a read happened but not reliably *who* did it. |
| 9 | No automatic PHI retention/deletion | Whole `cases` table and children | Medium (data minimization risk grows over time) | Partially addressed — `db/retention_job.py` exists as a manual, dry-run-by-default script; not yet scheduled, and the retention window is not yet set by a compliance owner. See `data_retention_policy.md`. |
| 10 | No rate limiting / retry backoff on the Anthropic API calls | `agents/claude_client.py` | Low/Medium (availability, not confidentiality) | Not mitigated. Phase 4. |
| 11 | DB connection helper opens/closes a raw connection per query, no pooling | `db/connection.py` | Low/Medium (availability under real concurrent load, not a PHI confidentiality risk directly) | Explicitly flagged in the code's own docstring as a known gap. Phase 4. |
| 12 | Extraction agent has no explicit allow-list restricting which categories of clinical detail it pulls (e.g. could pull substance-use or mental-health details that carry extra legal protection under 42 CFR Part 2) | `agents/extraction_agent.py` | Medium/High once real chart notes are used | Not mitigated — flagged in `phi_handling_policy.md`. |

## What this assessment does not cover

Workforce access management procedures, breach notification procedures,
disaster recovery / backup restoration testing, physical security of any
on-prem components, and sanctions policy for workforce violations — all
required elements of a full HIPAA Security Rule risk assessment that
depend on organizational policy, not this codebase.

## Recommended next step

Have this table reviewed and expanded by whoever will serve as the
organization's HIPAA Security Officer, cross-referenced against the
NIST SP 800-66 framework or an equivalent structured methodology, before
treating Phase 1 of `REAL_WORLD_DESIGN_PLAN.md` as complete.
