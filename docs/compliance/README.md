# Compliance documents — status

Everything in this directory is a **starting draft**, produced as part of
Phase 1 of `REAL_WORLD_DESIGN_PLAN.md`. None of it is a substitute for
review by qualified legal/compliance counsel, and none of it constitutes
an executed agreement. Specifically:

- `baa_tracking.md` is a checklist of what to confirm with each vendor.
  No BAA has been executed with any vendor as of this writing — that
  requires the practice's own outreach and signature, not something an
  AI assistant can do.
- `hipaa_risk_assessment.md` is a structured starting point covering this
  specific application's architecture and data flows. A real HIPAA risk
  assessment should be conducted or reviewed by someone with compliance
  expertise before it's relied on.
- `phi_handling_policy.md` and `data_retention_policy.md` are draft
  policies reflecting what the system currently does and a reasonable
  starting position — they need sign-off from whoever owns compliance
  for the deploying organization, and the retention window in particular
  needs a real legal answer (it varies by state and payer contract).

None of this work means real patient data is safe to put in this system.
Phase 1 of the design plan is explicit that it must be settled — with
real sign-off — before that happens.
