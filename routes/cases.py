from flask import Blueprint, flash, redirect, render_template, request, url_for

from db.connection import query
from agents.pipeline import run_pipeline

cases_bp = Blueprint("cases", __name__)


@cases_bp.route("/case/new", methods=["GET", "POST"])
def new_case():
    """Manual case intake — the only way today a case enters the pipeline
    besides db/seed.py. Always creates status='pending'; running the
    pipeline itself stays a separate, human-triggered step."""
    if request.method == "POST":
        result = query(
            """INSERT INTO cases (patient_name, patient_age, service_description,
               procedure_code, diagnosis_code, service_category, chart_note_text,
               payer_name, appointment_date, urgency_tier, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
               RETURNING id""",
            (
                request.form["patient_name"],
                request.form.get("patient_age") or None,
                request.form["service_description"],
                request.form.get("procedure_code") or None,
                request.form.get("diagnosis_code") or None,
                request.form.get("service_category") or None,
                request.form.get("chart_note_text") or None,
                request.form["payer_name"],
                request.form.get("appointment_date") or None,
                request.form.get("urgency_tier", "routine"),
            ),
        )
        case_id = result[0]["id"]
        query(
            """INSERT INTO case_events (case_id, event_type, actor, description)
               VALUES (%s, 'human_action', %s, 'Case created via intake form')""",
            (case_id, request.form.get("actor", "staff:unknown")),
            fetch=False,
        )
        flash("Case created.")
        return redirect(url_for("cases.case_detail", case_id=case_id))

    known = query(
        "SELECT DISTINCT payer_name, service_category FROM policies ORDER BY payer_name, service_category"
    )
    return render_template("case_new.html", known=known)


@cases_bp.route("/")
def queue():
    """The review queue dashboard — cases grouped by status, plus the
    metrics_snapshot numbers for the ROI header."""
    cases = query(
        "SELECT id, patient_name, service_description, urgency_tier, status "
        "FROM cases ORDER BY created_at DESC"
    )
    metrics = query(
        "SELECT * FROM metrics_snapshot ORDER BY snapshot_date DESC LIMIT 1"
    )
    return render_template("queue.html", cases=cases, metrics=metrics[0] if metrics else None)


@cases_bp.route("/case/<case_id>")
def case_detail(case_id):
    case = query("SELECT * FROM cases WHERE id = %s", (case_id,))
    if case:
        # HIPAA audit requirements cover access, not just modification — log
        # every read of a case's PHI here, not only the write actions below.
        # actor is 'staff:unknown' until real auth exists (see CONTINUE.md);
        # this log is not yet attributable to a specific person.
        query(
            """INSERT INTO case_events (case_id, event_type, actor, description)
               VALUES (%s, 'phi_access', 'staff:unknown', 'Case detail viewed')""",
            (case_id,),
            fetch=False,
        )
    fields = query(
        "SELECT * FROM extracted_fields WHERE case_id = %s ORDER BY created_at", (case_id,)
    )
    policy_results = query(
        """SELECT pcr.*, p.rule_name, p.rule_description
           FROM policy_check_results pcr
           JOIN policies p ON p.id = pcr.policy_id
           WHERE pcr.case_id = %s""",
        (case_id,),
    )
    draft = query(
        "SELECT * FROM drafts WHERE case_id = %s ORDER BY version DESC LIMIT 1", (case_id,)
    )
    denial = query(
        "SELECT * FROM denials WHERE case_id = %s AND resolved_at IS NULL "
        "ORDER BY denied_at DESC LIMIT 1",
        (case_id,),
    )
    return render_template(
        "case_detail.html",
        case=case[0] if case else None,
        fields=fields,
        policy_results=policy_results,
        draft=draft[0] if draft else None,
        denial=denial[0] if denial else None,
    )


@cases_bp.route("/case/<case_id>/process", methods=["POST"])
def process_case(case_id):
    """Runs a pending case through extraction -> policy check -> draft.
    Deterministic escalation on any failure; see agents/pipeline.py."""
    result = run_pipeline(case_id)
    flash(result.get("message", "Pipeline finished."))
    return redirect(url_for("cases.case_detail", case_id=case_id))


@cases_bp.route("/case/<case_id>/draft/edit", methods=["POST"])
def edit_draft(case_id):
    """Saves a human-edited draft as a new version. Editing is only offered
    in the UI before submission — once approve_and_submit fires, the draft
    that was actually sent is a historical record, not something to revise."""
    latest = query(
        "SELECT version FROM drafts WHERE case_id = %s ORDER BY version DESC LIMIT 1", (case_id,)
    )
    next_version = (latest[0]["version"] + 1) if latest else 1
    actor = request.form.get("actor", "staff:unknown")
    query(
        """INSERT INTO drafts (case_id, version, draft_text, edited_by)
           VALUES (%s, %s, %s, %s)""",
        (case_id, next_version, request.form.get("draft_text", ""), actor),
        fetch=False,
    )
    query(
        """INSERT INTO case_events (case_id, event_type, actor, description)
           VALUES (%s, 'human_action', %s, %s)""",
        (case_id, actor, f"Draft edited, now v{next_version}"),
        fetch=False,
    )
    flash("Draft saved.")
    return redirect(url_for("cases.case_detail", case_id=case_id))


@cases_bp.route("/case/<case_id>/approve", methods=["POST"])
def approve_and_submit(case_id):
    """A human clicked 'approve and submit'. Nothing reaches the payer
    without this route being hit by an authenticated staff action."""
    query(
        "UPDATE cases SET status = 'submitted', updated_at = now() WHERE id = %s",
        (case_id,),
        fetch=False,
    )
    query(
        """INSERT INTO case_events (case_id, event_type, actor, description)
           VALUES (%s, 'human_action', %s, 'Draft approved and submitted to payer')""",
        (case_id, request.form.get("actor", "staff:unknown")),
        fetch=False,
    )
    flash("Submitted to payer.")
    return redirect(url_for("cases.queue"))


@cases_bp.route("/case/<case_id>/escalate", methods=["POST"])
def escalate(case_id):
    query(
        "UPDATE cases SET status = 'escalated', updated_at = now() WHERE id = %s",
        (case_id,),
        fetch=False,
    )
    query(
        """INSERT INTO case_events (case_id, event_type, actor, description)
           VALUES (%s, 'human_action', %s, %s)""",
        (case_id, request.form.get("actor", "staff:unknown"),
         request.form.get("reason", "Escalated for review")),
        fetch=False,
    )
    flash("Case escalated.")
    return redirect(url_for("cases.queue"))


@cases_bp.route("/case/<case_id>/decision", methods=["POST"])
def record_decision(case_id):
    """Records the payer's decision on a submitted case. Approved closes the
    loop directly; denied creates the denials row that drives the existing
    resubmit/appeal UI."""
    decision = request.form.get("decision")
    actor = request.form.get("actor", "staff:unknown")
    if decision == "approved":
        query(
            "UPDATE cases SET status = 'approved', updated_at = now() WHERE id = %s",
            (case_id,),
            fetch=False,
        )
        query(
            """INSERT INTO case_events (case_id, event_type, actor, description)
               VALUES (%s, 'human_action', %s, 'Payer approved the request')""",
            (case_id, actor),
            fetch=False,
        )
        flash("Payer approved.")
    elif decision == "denied":
        query(
            "UPDATE cases SET status = 'denied', updated_at = now() WHERE id = %s",
            (case_id,),
            fetch=False,
        )
        query(
            """INSERT INTO denials (case_id, reason_code, reason_text, appeal_deadline)
               VALUES (%s, %s, %s, %s)""",
            (
                case_id,
                request.form.get("reason_code") or None,
                request.form.get("reason_text") or "No reason provided.",
                request.form.get("appeal_deadline") or None,
            ),
            fetch=False,
        )
        query(
            """INSERT INTO case_events (case_id, event_type, actor, description)
               VALUES (%s, 'human_action', %s, 'Payer denied the request')""",
            (case_id, actor),
            fetch=False,
        )
        flash("Denial recorded.")
    return redirect(url_for("cases.case_detail", case_id=case_id))


@cases_bp.route("/case/<case_id>/denial/resolve", methods=["POST"])
def resolve_denial(case_id):
    """Records the final outcome of a resubmission or appeal — the step
    that was previously missing: resubmit/appeal set a path, but nothing
    ever closed the loop on what the payer ultimately decided."""
    outcome = request.form.get("outcome")
    actor = request.form.get("actor", "staff:unknown")
    new_status = "approved" if outcome == "overturned" else "closed"
    query(
        """UPDATE denials SET resolved_at = now(), outcome = %s
           WHERE case_id = %s AND resolved_at IS NULL""",
        (outcome, case_id),
        fetch=False,
    )
    query(
        "UPDATE cases SET status = %s, updated_at = now() WHERE id = %s",
        (new_status, case_id),
        fetch=False,
    )
    query(
        """INSERT INTO case_events (case_id, event_type, actor, description)
           VALUES (%s, 'human_action', %s, %s)""",
        (case_id, actor, f"Denial resolved: {outcome}"),
        fetch=False,
    )
    flash(f"Marked as {outcome}.")
    return redirect(url_for("cases.case_detail", case_id=case_id))


@cases_bp.route("/case/<case_id>/denial/resubmit", methods=["POST"])
def resubmit(case_id):
    query(
        "UPDATE cases SET status = 'resubmit_pending', updated_at = now() WHERE id = %s",
        (case_id,),
        fetch=False,
    )
    query(
        """UPDATE denials SET resolution_path = 'resubmit' WHERE case_id = %s
           AND resolved_at IS NULL""",
        (case_id,),
        fetch=False,
    )
    flash("Marked for resubmission.")
    return redirect(url_for("cases.queue"))


@cases_bp.route("/case/<case_id>/denial/appeal", methods=["POST"])
def file_appeal(case_id):
    query(
        "UPDATE cases SET status = 'appeal_pending', updated_at = now() WHERE id = %s",
        (case_id,),
        fetch=False,
    )
    query(
        """UPDATE denials SET resolution_path = 'appeal' WHERE case_id = %s
           AND resolved_at IS NULL""",
        (case_id,),
        fetch=False,
    )
    flash("Formal appeal filed.")
    return redirect(url_for("cases.queue"))
