# Data retention & deletion policy (draft) — prior-auth-prep-agent

Status: **draft**. The retention window below is a placeholder, not legal
guidance — see `README.md` in this directory.

## What gets retained

Every `cases` row and its linked `case_events`, `extracted_fields`,
`policy_check_results`, `drafts`, and `denials` rows, for as long as the
case exists in the database. There is currently no automatic expiry.

## Proposed retention window

Deletion should trigger once a case reaches a terminal status
(`approved`, `denied`, or `closed`) and stays there past a retention
window. **The actual number of days must come from whoever owns
compliance for the deploying organization** — it depends on the
practice's state medical-record-retention statute (these vary widely,
commonly multi-year) and any retention terms in payer contracts. Do not
treat any specific number here as settled; `db/retention_job.py`
deliberately requires `--days` as an explicit argument with no default,
so this decision can't be silently skipped.

## Deletion mechanism

`db/retention_job.py` — a script, not yet a scheduled job. It:
1. Lists cases in a terminal status older than the given retention window
   (dry run by default).
2. Only deletes when run with `--confirm`.
3. Relies on `ON DELETE CASCADE` (already present in `db/schema.sql` on
   every table with a `case_id` foreign key) so deleting a `cases` row
   removes its full history in one transaction — no orphaned PHI left
   behind in child tables.

**Not yet done, needed before production:** wiring this into an actual
schedule (e.g. a daily Render cron job or scheduled task) instead of a
script someone has to remember to run, and deciding whether deleted cases
need to be archived somewhere (e.g. for the golden-set testing in Phase 5)
before they're purged, or genuinely destroyed with no copy retained.

## What does NOT get deleted by this job

`policies` (payer rule definitions) and `metrics_snapshot` (aggregate,
non-PHI numbers) are not case-linked PHI and are out of scope for this
job.
