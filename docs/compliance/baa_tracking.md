# BAA tracking checklist (draft) — prior-auth-prep-agent

Status: **nothing here is executed**. This is a checklist for the
practice/organization to work through directly with each vendor. An AI
assistant cannot sign or negotiate a contract on your behalf — see
`README.md` in this directory.

Every vendor in the stack that will touch real PHI needs a confirmed,
signed Business Associate Agreement before real patient data flows through
it. For each vendor below, confirm directly with them (their terms and
plan-tier requirements can change, and this document may be out of date by
the time you read it):

## Supabase (database)
- [ ] Confirm current plan tier requirements for a BAA (historically an
      add-on / higher-tier feature — verify current terms directly).
- [ ] Request and execute the BAA.
- [ ] Confirm which specific services are covered (e.g. Postgres, Auth,
      Storage) if only a subset of the product is in use.
- [ ] File the signed BAA somewhere durable (not just this repo).

## Render (hosting)
- [ ] Confirm current plan tier requirements for a BAA.
- [ ] Request and execute the BAA.
- [ ] Confirm whether the specific services used (web service, Postgres if
      used there instead of/alongside Supabase, background workers if
      added per Phase 4) are all covered.
- [ ] File the signed BAA.

## Anthropic (Claude API)
- [ ] Confirm current plan tier / API usage terms required for a BAA.
- [ ] Request and execute the BAA.
- [ ] Confirm zero-data-retention or data-handling terms for API calls, since
      chart-note text and extracted fields are sent to the API in
      `agents/extraction_agent.py`, `agents/policy_check_agent.py`, and
      `agents/draft_agent.py`.
- [ ] File the signed BAA.

## Before any of this is "done"
All three checkboxes' worth of agreements need to be in hand — not just
requested — before Phase 3 (real data integration) begins, per
`REAL_WORLD_DESIGN_PLAN.md`'s explicit ordering.
