"""
Pipeline orchestrator — the only place that calls the three agent functions
in sequence and moves a case's status forward.

The control flow here is plain Python, not an LLM decision: each agent is
called once per step, its output is written to the DB, and any failure
(malformed output, an API error, or a failed policy rule) routes the case
to 'escalated' rather than guessing or retrying silently.
"""
from db.connection import query
from agents.extraction_agent import extract_fields
from agents.policy_check_agent import check_policy, any_rule_failed
from agents.draft_agent import draft_submission


def _set_status(case_id, status):
    query(
        "UPDATE cases SET status = %s, updated_at = now() WHERE id = %s",
        (status, case_id),
        fetch=False,
    )


def _log(case_id, actor, description, event_type="agent_action"):
    query(
        """INSERT INTO case_events (case_id, event_type, actor, description)
           VALUES (%s, %s, %s, %s)""",
        (case_id, event_type, actor, description),
        fetch=False,
    )


def _escalate(case_id, reason):
    _set_status(case_id, "escalated")
    _log(case_id, "system", reason, event_type="status_change")
    return {"status": "escalated", "message": reason}


def run_pipeline(case_id):
    """Runs a pending case through extraction -> policy check -> draft.
    Returns a dict with the resulting status and a human-readable message,
    suitable for flashing straight to the review-queue UI."""
    rows = query("SELECT * FROM cases WHERE id = %s", (case_id,))
    if not rows:
        return {"status": "error", "message": "Case not found."}
    case = rows[0]

    if not case.get("chart_note_text"):
        return _escalate(case_id, "No chart note text on file — cannot run extraction.")

    # ---- extraction ---------------------------------------------------
    _set_status(case_id, "extracting")
    try:
        fields = extract_fields(case["chart_note_text"])
    except Exception as e:
        return _escalate(case_id, f"agent_error: extraction_agent raised {type(e).__name__}")

    if not fields:
        return _escalate(
            case_id,
            "Extraction agent returned no fields — chart note may be missing required information.",
        )

    for f in fields:
        query(
            """INSERT INTO extracted_fields (case_id, field_name, field_value, source_note)
               VALUES (%s, %s, %s, %s)""",
            (case_id, f.get("field_name", ""), f.get("field_value", ""), f.get("source_note")),
            fetch=False,
        )
    _log(case_id, "extraction_agent", f"Extracted {len(fields)} field(s) from chart note")

    # ---- policy check ---------------------------------------------------
    _set_status(case_id, "policy_check")
    policies = query(
        "SELECT * FROM policies WHERE payer_name = %s AND service_category = %s",
        (case["payer_name"], case["service_category"]),
    )
    if not policies:
        return _escalate(
            case_id,
            f"No policy rules on file for {case['payer_name']} / {case['service_category']}.",
        )

    rule_payload = [
        {"rule_name": p["rule_name"], "rule_description": p["rule_description"]} for p in policies
    ]
    try:
        results = check_policy(fields, rule_payload)
    except Exception as e:
        return _escalate(case_id, f"agent_error: policy_check_agent raised {type(e).__name__}")

    policy_by_name = {p["rule_name"]: p for p in policies}
    for r in results:
        policy = policy_by_name.get(r.get("rule_name"))
        if not policy:
            continue
        query(
            """INSERT INTO policy_check_results (case_id, policy_id, passed, notes)
               VALUES (%s, %s, %s, %s)""",
            (case_id, policy["id"], bool(r.get("passed", False)), r.get("notes")),
            fetch=False,
        )

    if any_rule_failed(results):
        failed = [r.get("rule_name", "?") for r in results if not r.get("passed", False)]
        reason = (
            f"Policy check failed: {', '.join(failed)}"
            if failed
            else "Policy check agent returned no usable results."
        )
        return _escalate(case_id, reason)
    _log(case_id, "policy_check_agent", f"All {len(results)} policy rule(s) passed")

    # ---- draft ---------------------------------------------------
    _set_status(case_id, "draft_ready")
    case_summary = {
        "patient_age": case["patient_age"],
        "service_description": case["service_description"],
        "diagnosis_code": case["diagnosis_code"],
        "procedure_code": case["procedure_code"],
        "extracted_fields": fields,
        "policy_notes": [r.get("notes") for r in results],
    }
    try:
        draft_text = draft_submission(case_summary)
    except Exception as e:
        return _escalate(case_id, f"agent_error: draft_agent raised {type(e).__name__}")

    query(
        "INSERT INTO drafts (case_id, version, draft_text) VALUES (%s, 1, %s)",
        (case_id, draft_text),
        fetch=False,
    )
    _log(case_id, "draft_agent", "Draft submission generated")

    _set_status(case_id, "needs_review")
    _log(case_id, "system", "Pipeline complete — ready for human review", event_type="status_change")
    return {"status": "needs_review", "message": "Pipeline complete — draft ready for review."}
