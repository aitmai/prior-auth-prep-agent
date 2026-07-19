-- Prior Authorization Prep Agent — schema.sql
-- Run against a fresh Postgres database (Render Postgres or local).
-- All patient/case data in this schema is intended to hold SYNTHETIC data only.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing tables — safe to rerun during prototyping since this schema
-- is documented to hold synthetic data only. Order doesn't matter (CASCADE).
DROP TABLE IF EXISTS metrics_snapshot CASCADE;
DROP TABLE IF EXISTS denials CASCADE;
DROP TABLE IF EXISTS drafts CASCADE;
DROP TABLE IF EXISTS policy_check_results CASCADE;
DROP TABLE IF EXISTS policies CASCADE;
DROP TABLE IF EXISTS extracted_fields CASCADE;
DROP TABLE IF EXISTS case_events CASCADE;
DROP TABLE IF EXISTS cases CASCADE;

-- ---------------------------------------------------------------------------
-- cases: one row per prior authorization request, from scheduling to close
-- ---------------------------------------------------------------------------
CREATE TABLE cases (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    patient_name        VARCHAR(120)    NOT NULL,   -- synthetic data only
    patient_age         INTEGER,
    service_description VARCHAR(255)    NOT NULL,
    procedure_code      VARCHAR(20),                -- CPT / HCPCS
    diagnosis_code      VARCHAR(20),                -- ICD-10
    service_category    VARCHAR(120),                -- matches policies.service_category
    chart_note_text     TEXT,                        -- raw intake note fed to the extraction agent
    payer_name          VARCHAR(120)    NOT NULL,
    appointment_date    DATE,
    urgency_tier        VARCHAR(20)     NOT NULL DEFAULT 'routine'
                        CHECK (urgency_tier IN ('routine', 'urgent')),
    status              VARCHAR(30)     NOT NULL DEFAULT 'pending'
                        CHECK (status IN (
                            'pending', 'extracting', 'policy_check',
                            'draft_ready', 'needs_review', 'escalated',
                            'submitted', 'approved', 'denied',
                            'resubmit_pending', 'appeal_pending', 'closed'
                        )),
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX idx_cases_status ON cases(status);
CREATE INDEX idx_cases_payer ON cases(payer_name);

-- ---------------------------------------------------------------------------
-- case_events: append-only audit trail — every agent and human action
-- ---------------------------------------------------------------------------
CREATE TABLE case_events (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id      UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    event_type   VARCHAR(30) NOT NULL
                 CHECK (event_type IN ('agent_action', 'human_action', 'status_change', 'phi_access')),
    actor        VARCHAR(60) NOT NULL,   -- e.g. 'extraction_agent', 'staff:jdoe'
    description  TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_case_events_case_id ON case_events(case_id);

-- ---------------------------------------------------------------------------
-- extracted_fields: structured output from the extraction agent
-- ---------------------------------------------------------------------------
CREATE TABLE extracted_fields (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id      UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    field_name   VARCHAR(120) NOT NULL,
    field_value  TEXT NOT NULL,
    source_note  VARCHAR(255),           -- where in the chart this came from
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_extracted_fields_case_id ON extracted_fields(case_id);

-- ---------------------------------------------------------------------------
-- policies: payer-specific rules the policy check agent evaluates against
-- ---------------------------------------------------------------------------
CREATE TABLE policies (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    payer_name        VARCHAR(120) NOT NULL,
    service_category  VARCHAR(120) NOT NULL,   -- e.g. 'biologic_infusion', 'imaging_mri'
    rule_name         VARCHAR(120) NOT NULL,
    rule_description  TEXT NOT NULL,
    is_required       BOOLEAN NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_policies_payer_category ON policies(payer_name, service_category);

-- ---------------------------------------------------------------------------
-- policy_check_results: outcome of checking one case against one policy rule
-- ---------------------------------------------------------------------------
CREATE TABLE policy_check_results (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id      UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    policy_id    UUID NOT NULL REFERENCES policies(id),
    passed       BOOLEAN NOT NULL,
    notes        TEXT,
    checked_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_policy_check_results_case_id ON policy_check_results(case_id);

-- ---------------------------------------------------------------------------
-- drafts: versioned submission text prepared by the draft agent
-- ---------------------------------------------------------------------------
CREATE TABLE drafts (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id      UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    version      INTEGER NOT NULL DEFAULT 1,
    draft_text   TEXT NOT NULL,
    edited_by    VARCHAR(60),           -- null if agent-authored, unedited
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_drafts_case_id ON drafts(case_id);

-- ---------------------------------------------------------------------------
-- denials: tracks a denied case through resubmission or appeal
-- ---------------------------------------------------------------------------
CREATE TABLE denials (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id           UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    reason_code       VARCHAR(60),
    reason_text       TEXT NOT NULL,
    denied_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    appeal_deadline   DATE,
    resolution_path   VARCHAR(20)
                      CHECK (resolution_path IN ('resubmit', 'appeal', 'peer_to_peer', NULL)),
    resolved_at       TIMESTAMPTZ,
    outcome           VARCHAR(20)
                      CHECK (outcome IN ('overturned', 'upheld', NULL))
);

CREATE INDEX idx_denials_case_id ON denials(case_id);

-- ---------------------------------------------------------------------------
-- metrics_snapshot: rolling stats for the ROI dashboard
-- ---------------------------------------------------------------------------
CREATE TABLE metrics_snapshot (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_date         DATE NOT NULL DEFAULT CURRENT_DATE,
    avg_minutes_per_case  NUMERIC(6,2),
    escalation_rate       NUMERIC(5,2),   -- percentage, e.g. 18.00
    completion_rate       NUMERIC(5,2),
    cases_completed       INTEGER NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX idx_metrics_snapshot_date ON metrics_snapshot(snapshot_date);
