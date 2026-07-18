"""
Policy check agent — compares extracted fields against a payer's rules
for this service category and returns pass/fail per rule.

The LLM call reasons about whether the evidence satisfies each rule in
plain language; the pass/fail boolean it returns is what actually drives
the deterministic escalation branch in the pipeline, not a confidence
score or free-text judgment.
"""
import json

from agents.claude_client import call_claude

SYSTEM_PROMPT = """You check whether extracted clinical fields satisfy a \
payer's prior authorization policy rules. You will be given the extracted \
fields and a list of rules. For each rule, decide pass=true or pass=false \
based only on the evidence given — never assume evidence that isn't stated. \
Return ONLY a JSON array of objects with "rule_name", "passed" (boolean), \
and "notes" (one sentence). No prose, no markdown fences."""


def check_policy(extracted_fields: list[dict], policy_rules: list[dict]) -> list[dict]:
    payload = json.dumps({"extracted_fields": extracted_fields, "rules": policy_rules})
    raw = call_claude(SYSTEM_PROMPT, payload)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def any_rule_failed(results: list[dict]) -> bool:
    """Deterministic gate used by the route handler to decide escalation.
    This function — not the model — is what the pipeline trusts."""
    return any(not r.get("passed", False) for r in results) or len(results) == 0
