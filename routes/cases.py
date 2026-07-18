from flask import Blueprint, flash, redirect, render_template, request, url_for

from db.connection import query

cases_bp = Blueprint("cases", __name__)


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
