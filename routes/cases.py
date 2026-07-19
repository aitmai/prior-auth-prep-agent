from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from db.connection import query
from agents.pipeline import run_pipeline

cases_bp = Blueprint("cases", __name__)

# Curated, not comprehensive — real CPT/ICD-10 code sets run into the tens
# of thousands and nothing in this app has that reference data loaded. This
# covers the codes already used by the seed data/policies, plus an "Other"
# fallback on the form for anything not listed.
PROCEDURE_CODES = [
    ("J1745", "Biologic infusion, remicade"),
    ("J0135", "Biologic infusion, humira"),
    ("72148", "MRI lumbar spine"),
    ("73721", "MRI lower extremity joint"),
    ("97110", "Physical therapy, therapeutic exercise"),
    ("74177", "CT abdomen w/ contrast"),
    ("71260", "CT chest w/ contrast"),
]
DIAGNOSIS_CODES = [
    ("M06.9", "Rheumatoid arthritis, unspecified"),
    ("M05.79", "Rheumatoid arthritis with rheumatoid factor, multiple sites"),
    ("M54.16", "Radiculopathy, lumbar region"),
    ("M23.51", "Sprain of medial collateral ligament, right knee"),
    ("M25.561", "Pain in right knee"),
    ("M54.5", "Low back pain"),
    ("R10.9", "Unspecified abdominal pain"),
    ("R91.8", "Other nonspecific abnormal finding of lung field"),
]


def _resolve_choice(form, field, other_field):
    """Server-side resolution of a <select> + free-text 'Other' pair — no
    JS needed. The custom text field wins if filled in; otherwise the
    select's value is used unless it's the '__other__' placeholder."""
    other = (form.get(other_field) or "").strip()
    if other:
        return other
    val = form.get(field, "")
    return val if val and val != "__other__" else None


def _payer_and_category_options():
    known = query(
        "SELECT DISTINCT payer_name, service_category FROM policies ORDER BY payer_name, service_category"
    )
    payers = sorted({k["payer_name"] for k in known})
    categories = sorted({k["service_category"] for k in known})
    return payers, categories


def _case_form_context(**overrides):
    payers, categories = _payer_and_category_options()
    context = dict(
        payers=payers,
        categories=categories,
        procedure_codes=PROCEDURE_CODES,
        procedure_code_values=[c for c, _ in PROCEDURE_CODES],
        diagnosis_codes=DIAGNOSIS_CODES,
        diagnosis_code_values=[c for c, _ in DIAGNOSIS_CODES],
        appointments=[],
        prefill_appointment_id=None,
    )
    context.update(overrides)
    return context


@cases_bp.route("/case/new", methods=["GET", "POST"])
@login_required
def new_case():
    """Manual case intake — the only way today a case enters the pipeline
    besides db/seed.py. Always creates status='pending'; running the
    pipeline itself stays a separate, human-triggered step. Can optionally
    pre-fill from a mock scheduled_appointments row (see schema.sql — a
    stand-in for real Phase 3 EHR/scheduling integration)."""
    if request.method == "POST":
        patient_name = request.form.get("patient_name", "").strip()
        service_description = request.form.get("service_description", "").strip()
        payer_name = _resolve_choice(request.form, "payer_name", "payer_name_other")
        if not patient_name or not service_description or not payer_name:
            flash("Patient name, service description, and payer are required.")
            return redirect(url_for("cases.new_case"))

        result = query(
            """INSERT INTO cases (patient_name, patient_age, service_description,
               procedure_code, diagnosis_code, service_category, chart_note_text,
               payer_name, appointment_date, urgency_tier, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
               RETURNING id""",
            (
                patient_name,
                request.form.get("patient_age") or None,
                service_description,
                _resolve_choice(request.form, "procedure_code", "procedure_code_other"),
                _resolve_choice(request.form, "diagnosis_code", "diagnosis_code_other"),
                _resolve_choice(request.form, "service_category", "service_category_other"),
                request.form.get("chart_note_text") or None,
                payer_name,
                request.form.get("appointment_date") or None,
                request.form.get("urgency_tier", "routine"),
            ),
        )
        case_id = result[0]["id"]
        query(
            """INSERT INTO case_events (case_id, event_type, actor, description)
               VALUES (%s, 'human_action', %s, 'Case created via intake form')""",
            (case_id, current_user.actor),
            fetch=False,
        )
        appointment_id = request.form.get("appointment_id")
        if appointment_id:
            query(
                "UPDATE scheduled_appointments SET used_at = now() WHERE id = %s",
                (appointment_id,),
                fetch=False,
            )
        flash("Case created.")
        return redirect(url_for("cases.case_detail", case_id=case_id))

    prefill = {}
    prefill_appointment_id = None
    from_appointment = request.args.get("from_appointment")
    if from_appointment:
        rows = query(
            "SELECT * FROM scheduled_appointments WHERE id = %s AND used_at IS NULL",
            (from_appointment,),
        )
        if rows:
            prefill = rows[0]
            prefill_appointment_id = rows[0]["id"]
        else:
            flash("That scheduled appointment is no longer available.")

    appointments = query(
        "SELECT * FROM scheduled_appointments WHERE used_at IS NULL ORDER BY appointment_date"
    )

    return render_template(
        "case_form.html",
        mode="new",
        case=None,
        data=prefill,
        **_case_form_context(appointments=appointments, prefill_appointment_id=prefill_appointment_id),
    )


@cases_bp.route("/case/<case_id>/edit", methods=["GET", "POST"])
@login_required
def edit_case(case_id):
    """Editing is only offered while a case is 'pending' — once extraction/
    policy check/draft exist, they'd reference stale data if the case's
    core facts changed underneath them."""
    rows = query("SELECT * FROM cases WHERE id = %s", (case_id,))
    if not rows:
        flash("Case not found.")
        return redirect(url_for("cases.queue"))
    case = rows[0]
    if case["status"] != "pending":
        flash("Case can only be edited while pending.")
        return redirect(url_for("cases.case_detail", case_id=case_id))

    if request.method == "POST":
        patient_name = request.form.get("patient_name", "").strip()
        service_description = request.form.get("service_description", "").strip()
        payer_name = _resolve_choice(request.form, "payer_name", "payer_name_other")
        if not patient_name or not service_description or not payer_name:
            flash("Patient name, service description, and payer are required.")
            return redirect(url_for("cases.edit_case", case_id=case_id))

        query(
            """UPDATE cases SET patient_name = %s, patient_age = %s, service_description = %s,
               procedure_code = %s, diagnosis_code = %s, service_category = %s,
               chart_note_text = %s, payer_name = %s, appointment_date = %s,
               urgency_tier = %s, updated_at = now()
               WHERE id = %s""",
            (
                patient_name,
                request.form.get("patient_age") or None,
                service_description,
                _resolve_choice(request.form, "procedure_code", "procedure_code_other"),
                _resolve_choice(request.form, "diagnosis_code", "diagnosis_code_other"),
                _resolve_choice(request.form, "service_category", "service_category_other"),
                request.form.get("chart_note_text") or None,
                payer_name,
                request.form.get("appointment_date") or None,
                request.form.get("urgency_tier", "routine"),
                case_id,
            ),
            fetch=False,
        )
        query(
            """INSERT INTO case_events (case_id, event_type, actor, description)
               VALUES (%s, 'human_action', %s, 'Case details edited via form')""",
            (case_id, current_user.actor),
            fetch=False,
        )
        flash("Case updated.")
        return redirect(url_for("cases.case_detail", case_id=case_id))

    return render_template(
        "case_form.html",
        mode="edit",
        case=case,
        data=case,
        **_case_form_context(),
    )


@cases_bp.route("/")
@login_required
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
@login_required
def case_detail(case_id):
    case = query("SELECT * FROM cases WHERE id = %s", (case_id,))
    if case:
        # HIPAA audit requirements cover access, not just modification — log
        # every read of a case's PHI here, not only the write actions below.
        # Now attributable to a real logged-in user, not a placeholder.
        query(
            """INSERT INTO case_events (case_id, event_type, actor, description)
               VALUES (%s, 'phi_access', %s, 'Case detail viewed')""",
            (case_id, current_user.actor),
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
@login_required
def process_case(case_id):
    """Runs a pending case through extraction -> policy check -> draft.
    Deterministic escalation on any failure; see agents/pipeline.py."""
    result = run_pipeline(case_id)
    flash(result.get("message", "Pipeline finished."))
    return redirect(url_for("cases.case_detail", case_id=case_id))


@cases_bp.route("/case/<case_id>/draft/edit", methods=["POST"])
@login_required
def edit_draft(case_id):
    """Saves a human-edited draft as a new version. Editing is only offered
    in the UI before submission — once approve_and_submit fires, the draft
    that was actually sent is a historical record, not something to revise."""
    latest = query(
        "SELECT version FROM drafts WHERE case_id = %s ORDER BY version DESC LIMIT 1", (case_id,)
    )
    next_version = (latest[0]["version"] + 1) if latest else 1
    actor = current_user.actor
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
@login_required
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
        (case_id, current_user.actor),
        fetch=False,
    )
    flash("Submitted to payer.")
    return redirect(url_for("cases.queue"))


@cases_bp.route("/case/<case_id>/escalate", methods=["POST"])
@login_required
def escalate(case_id):
    query(
        "UPDATE cases SET status = 'escalated', updated_at = now() WHERE id = %s",
        (case_id,),
        fetch=False,
    )
    query(
        """INSERT INTO case_events (case_id, event_type, actor, description)
           VALUES (%s, 'human_action', %s, %s)""",
        (case_id, current_user.actor,
         request.form.get("reason", "Escalated for review")),
        fetch=False,
    )
    flash("Case escalated.")
    return redirect(url_for("cases.queue"))


@cases_bp.route("/case/<case_id>/decision", methods=["POST"])
@login_required
def record_decision(case_id):
    """Records the payer's decision on a submitted case. Approved closes the
    loop directly; denied creates the denials row that drives the existing
    resubmit/appeal UI."""
    decision = request.form.get("decision")
    actor = current_user.actor
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
@login_required
def resolve_denial(case_id):
    """Records the final outcome of a resubmission or appeal — the step
    that was previously missing: resubmit/appeal set a path, but nothing
    ever closed the loop on what the payer ultimately decided."""
    outcome = request.form.get("outcome")
    actor = current_user.actor
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
@login_required
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
    query(
        """INSERT INTO case_events (case_id, event_type, actor, description)
           VALUES (%s, 'human_action', %s, 'Marked for resubmission')""",
        (case_id, current_user.actor),
        fetch=False,
    )
    flash("Marked for resubmission.")
    return redirect(url_for("cases.queue"))


@cases_bp.route("/case/<case_id>/denial/appeal", methods=["POST"])
@login_required
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
    query(
        """INSERT INTO case_events (case_id, event_type, actor, description)
           VALUES (%s, 'human_action', %s, 'Formal appeal filed')""",
        (case_id, current_user.actor),
        fetch=False,
    )
    flash("Formal appeal filed.")
    return redirect(url_for("cases.queue"))
