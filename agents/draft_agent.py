"""
Draft agent — writes the prior authorization submission text once a case
has passed policy check. Its output is always a proposal for a human to
review, edit, or reject — never sent automatically.
"""
from agents.claude_client import call_claude

SYSTEM_PROMPT = """You write concise, factual prior authorization request \
narratives for payer submission. Use only the extracted fields and policy \
notes given to you — never invent clinical details. Keep it to 3-4 \
sentences: diagnosis, relevant history, why the requested service meets \
the payer's policy. Plain text only, no headers, no markdown."""


def draft_submission(case_summary: dict) -> str:
    """case_summary should include patient/diagnosis info, extracted
    fields, and policy check notes — everything needed to justify the
    request without the agent inferring anything new."""
    import json
    return call_claude(SYSTEM_PROMPT, json.dumps(case_summary))
