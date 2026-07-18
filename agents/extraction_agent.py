"""
Extraction agent — reads a chart note / referral text and pulls out the
structured fields a prior authorization request needs.

Deliberately narrow: this agent only extracts. It does not judge whether
the case meets payer policy (that's policy_check_agent) and does not
write the submission (that's draft_agent).
"""
from agents.claude_client import call_claude, parse_json_array

SYSTEM_PROMPT = """You extract structured fields from clinical chart notes \
for prior authorization requests. Return ONLY a JSON array of objects, each \
with "field_name", "field_value", and "source_note" keys. No prose, no \
markdown fences. If a required field is not found in the note, omit it \
rather than guessing."""


def extract_fields(chart_note_text: str) -> list[dict]:
    raw = call_claude(SYSTEM_PROMPT, chart_note_text)
    # Malformed model output surfaces as a review case, not a crash — the
    # pipeline routes an empty result to escalation.
    result = parse_json_array(raw)
    return result if result is not None else []
