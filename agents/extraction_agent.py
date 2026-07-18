"""
Extraction agent — reads a chart note / referral text and pulls out the
structured fields a prior authorization request needs.

Deliberately narrow: this agent only extracts. It does not judge whether
the case meets payer policy (that's policy_check_agent) and does not
write the submission (that's draft_agent).
"""
import json

from agents.claude_client import call_claude

SYSTEM_PROMPT = """You extract structured fields from clinical chart notes \
for prior authorization requests. Return ONLY a JSON array of objects, each \
with "field_name", "field_value", and "source_note" keys. No prose, no \
markdown fences. If a required field is not found in the note, omit it \
rather than guessing."""


def extract_fields(chart_note_text: str) -> list[dict]:
    raw = call_claude(SYSTEM_PROMPT, chart_note_text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Malformed model output should surface as a review case, not crash
        # the pipeline. Calling code should log this and route to escalation.
        return []
