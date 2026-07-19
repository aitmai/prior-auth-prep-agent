"""
Seed script — populates the database with synthetic demo data.
All patient names/details below are FAKE, for demo purposes only.

Usage:
    python db/seed.py
Requires DATABASE_URL in the environment (see .env.example).
"""
import os
import uuid
from datetime import date, timedelta

import psycopg2
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]


def run():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # ---- demo users — LOCAL DEMO ONLY. These are throwaway passwords for
    # a prototype with no real patients; never reuse this pattern once real
    # PHI is in play. See docs/compliance/hipaa_risk_assessment.md, risk #1. --
    users = [
        ("staff1", "staffdemo123", "staff"),
        ("supervisor1", "supervisordemo123", "supervisor"),
        ("admin1", "admindemo123", "admin"),
    ]
    for username, password, role in users:
        cur.execute(
            """INSERT INTO users (username, password_hash, role)
               VALUES (%s, %s, %s)""",
            (username, generate_password_hash(password), role),
        )

    # ---- policies (payer rules) -------------------------------------------------
    policies = [
        ("Aetna PPO", "biologic_infusion", "step_therapy",
         "Patient must have tried and failed at least one conventional DMARD "
         "(e.g. methotrexate) for a minimum of 3 months before biologic approval.", True),
        ("Aetna PPO", "biologic_infusion", "site_of_care",
         "Infusion must occur at an approved outpatient infusion center, not "
         "home infusion, for this plan tier.", True),
        ("Aetna PPO", "imaging_mri", "conservative_treatment_first",
         "Patient must show 6 weeks of conservative treatment (PT, NSAIDs) "
         "documented before advanced imaging is approved.", True),
        ("UnitedHealthcare", "imaging_ct", "clinical_justification",
         "Requires documented clinical indication consistent with ACR "
         "appropriateness criteria for contrast CT.", True),
        ("Cigna", "physical_therapy", "visit_cap",
         "Initial authorization capped at 12 visits; additional visits require "
         "a progress note showing functional improvement.", True),
    ]
    policy_ids = {}
    for payer, category, rule_name, desc, required in policies:
        pid = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO policies (id, payer_name, service_category, rule_name,
               rule_description, is_required) VALUES (%s, %s, %s, %s, %s, %s)""",
            (pid, payer, category, rule_name, desc, required),
        )
        policy_ids[(payer, category, rule_name)] = pid

    # ---- cases --------------------------------------------------------------
    today = date.today()
    cases = [
        dict(patient_name="M. Alvarez", patient_age=54,
             service_description="Biologic infusion, remicade",
             procedure_code="J1745", diagnosis_code="M06.9",
             service_category="biologic_infusion",
             payer_name="Aetna PPO", appointment_date=today + timedelta(days=16),
             urgency_tier="routine", status="needs_review"),
        dict(patient_name="R. Kim", patient_age=61,
             service_description="MRI lumbar spine",
             procedure_code="72148", diagnosis_code="M54.16",
             service_category="imaging_mri",
             chart_note_text=(
                 "Patient reports 8 weeks of lower back pain radiating to left leg. "
                 "Conservative treatment attempted: physical therapy 2x/week for 6 "
                 "weeks, plus NSAIDs (ibuprofen 600mg) with minimal improvement. "
                 "Straight leg raise positive on left. Ordering physician: Dr. A. "
                 "Reyes, NPI 9876543210. Requesting MRI lumbar spine to evaluate for "
                 "disc herniation prior to specialist referral."
             ),
             payer_name="Aetna PPO", appointment_date=today + timedelta(days=3),
             urgency_tier="urgent", status="pending"),
        dict(patient_name="J. Patel", patient_age=47,
             service_description="Physical therapy, 12 visits",
             procedure_code="97110", diagnosis_code="M25.561",
             service_category="physical_therapy",
             chart_note_text=(
                 "Patient presents with right knee pain following a meniscus strain, "
                 "diagnosis M25.561. No prior physical therapy for this episode. "
                 "Ordering physician recommends an initial course of physical "
                 "therapy, 12 visits, to improve range of motion and reduce pain "
                 "prior to considering further intervention. Ordering physician: "
                 "Dr. L. Chen, NPI 1122334455."
             ),
             payer_name="Cigna", appointment_date=today + timedelta(days=10),
             urgency_tier="routine", status="pending"),
        dict(patient_name="D. Nguyen", patient_age=39,
             service_description="CT abdomen w/ contrast",
             procedure_code="74177", diagnosis_code="R10.9",
             service_category="imaging_ct",
             payer_name="UnitedHealthcare", appointment_date=today + timedelta(days=7),
             urgency_tier="routine", status="needs_review"),
        dict(patient_name="S. Brooks", patient_age=58,
             service_description="Biologic infusion, missing clinical notes",
             procedure_code="J1745", diagnosis_code="M06.9",
             service_category="biologic_infusion",
             payer_name="Aetna PPO", appointment_date=today + timedelta(days=5),
             urgency_tier="urgent", status="escalated"),
        dict(patient_name="A. Ferreira", patient_age=44,
             service_description="Biologic infusion, remicade",
             procedure_code="J1745", diagnosis_code="M06.9",
             service_category="biologic_infusion",
             payer_name="Aetna PPO", appointment_date=today - timedelta(days=2),
             urgency_tier="routine", status="submitted"),
    ]

    case_ids = {}
    for c in cases:
        cid = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO cases (id, patient_name, patient_age, service_description,
               procedure_code, diagnosis_code, service_category, chart_note_text,
               payer_name, appointment_date, urgency_tier, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (cid, c["patient_name"], c["patient_age"], c["service_description"],
             c["procedure_code"], c["diagnosis_code"], c["service_category"],
             c.get("chart_note_text"), c["payer_name"],
             c["appointment_date"], c["urgency_tier"], c["status"]),
        )
        case_ids[c["patient_name"]] = cid
        cur.execute(
            """INSERT INTO case_events (case_id, event_type, actor, description)
               VALUES (%s, 'status_change', 'system', %s)""",
            (cid, f"Case created with status {c['status']}"),
        )

    # ---- extracted fields for the Alvarez case (matches the case detail mockup) --
    alvarez_id = case_ids["M. Alvarez"]
    fields = [
        ("Diagnosis", "Rheumatoid arthritis, ICD-10 M06.9", "Problem list"),
        ("Prior therapy tried", "Methotrexate, 6 months, inadequate response", "Progress note, Jun 28"),
        ("Ordering physician NPI", "1234567890", "Referral order"),
    ]
    for name, value, source in fields:
        cur.execute(
            """INSERT INTO extracted_fields (case_id, field_name, field_value, source_note)
               VALUES (%s, %s, %s, %s)""",
            (alvarez_id, name, value, source),
        )

    # ---- policy check results for Alvarez -----------------------------------
    for key in [("Aetna PPO", "biologic_infusion", "step_therapy"),
                ("Aetna PPO", "biologic_infusion", "site_of_care")]:
        cur.execute(
            """INSERT INTO policy_check_results (case_id, policy_id, passed, notes)
               VALUES (%s, %s, %s, %s)""",
            (alvarez_id, policy_ids[key], True, "Requirement met per chart review."),
        )

    # ---- draft for Alvarez ---------------------------------------------------
    cur.execute(
        """INSERT INTO drafts (case_id, version, draft_text)
           VALUES (%s, 1, %s)""",
        (alvarez_id,
         "Requesting prior authorization for infliximab infusion for member "
         "M. Alvarez, dx M06.9. Patient completed 6-month methotrexate trial "
         "without adequate response. Requesting approval for ongoing biologic "
         "therapy per plan step-therapy policy."),
    )

    # ---- a denied case with an active appeal window --------------------------
    brooks_id = case_ids["S. Brooks"]
    cur.execute(
        """UPDATE cases SET status = 'escalated' WHERE id = %s""",
        (brooks_id,),
    )
    cur.execute(
        """INSERT INTO denials (case_id, reason_code, reason_text, appeal_deadline, resolution_path)
           VALUES (%s, %s, %s, %s, %s)""",
        (brooks_id, "INSUFFICIENT_DOCS",
         "Insufficient documentation of prior therapy failure. Methotrexate "
         "trial duration not specified in submitted records.",
         today + timedelta(days=6), "resubmit"),
    )

    # ---- mock scheduled appointments (stand-in for a real EHR/scheduling
    # system — see the comment on scheduled_appointments in schema.sql) -----
    appointments = [
        dict(patient_name="K. Whitfield", patient_age=66,
             service_description="Biologic infusion, humira",
             procedure_code="J0135", diagnosis_code="M05.79",
             service_category="biologic_infusion", payer_name="Aetna PPO",
             appointment_date=today + timedelta(days=12), urgency_tier="routine",
             chart_note_text=(
                 "Patient with seropositive rheumatoid arthritis, multiple "
                 "joints. Completed 4-month methotrexate trial, inadequate "
                 "response per rheumatology progress note. Ordering "
                 "physician: Dr. S. Patel, NPI 3344556677. Requesting "
                 "biologic infusion (adalimumab) per step-therapy policy."
             )),
        dict(patient_name="B. Alvarado", patient_age=34,
             service_description="MRI knee, right",
             procedure_code="73721", diagnosis_code="M23.51",
             service_category="imaging_mri", payer_name="Aetna PPO",
             appointment_date=today + timedelta(days=8), urgency_tier="routine",
             chart_note_text=(
                 "Patient with right knee pain and instability x10 weeks "
                 "following a twisting injury. Completed 6 weeks of physical "
                 "therapy and NSAIDs with persistent instability on exam. "
                 "Ordering physician: Dr. M. Alavi, NPI 2233445566. "
                 "Requesting MRI right knee to evaluate for ligament injury."
             )),
        dict(patient_name="N. Osei", patient_age=29,
             service_description="CT chest w/ contrast",
             procedure_code="71260", diagnosis_code="R91.8",
             service_category="imaging_ct", payer_name="UnitedHealthcare",
             appointment_date=today + timedelta(days=5), urgency_tier="urgent",
             chart_note_text=(
                 "Patient with abnormal finding on chest X-ray, indeterminate "
                 "pulmonary nodule. Ordering physician recommends contrast CT "
                 "chest for further characterization per ACR appropriateness "
                 "criteria. Ordering physician: Dr. T. Nakamura, NPI 4455667788."
             )),
        dict(patient_name="F. Delgado", patient_age=52,
             service_description="Physical therapy, 12 visits",
             procedure_code="97110", diagnosis_code="M54.5",
             service_category="physical_therapy", payer_name="Cigna",
             appointment_date=today + timedelta(days=9), urgency_tier="routine",
             chart_note_text=(
                 "Patient with chronic low back pain, no prior physical "
                 "therapy for this episode. Ordering physician recommends an "
                 "initial course of physical therapy, 12 visits, to reduce "
                 "pain and improve function. Ordering physician: Dr. J. Wren, "
                 "NPI 5566778899."
             )),
    ]
    for a in appointments:
        cur.execute(
            """INSERT INTO scheduled_appointments (patient_name, patient_age,
               service_description, procedure_code, diagnosis_code, service_category,
               payer_name, appointment_date, urgency_tier, chart_note_text)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (a["patient_name"], a["patient_age"], a["service_description"],
             a["procedure_code"], a["diagnosis_code"], a["service_category"],
             a["payer_name"], a["appointment_date"], a["urgency_tier"],
             a["chart_note_text"]),
        )

    # ---- one metrics snapshot for the dashboard -------------------------------
    cur.execute(
        """INSERT INTO metrics_snapshot (snapshot_date, avg_minutes_per_case,
           escalation_rate, completion_rate, cases_completed)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (snapshot_date) DO NOTHING""",
        (today, 11.0, 18.0, 82.0, 27),
    )

    conn.commit()
    cur.close()
    conn.close()
    print("Seed data loaded successfully.")


if __name__ == "__main__":
    run()
