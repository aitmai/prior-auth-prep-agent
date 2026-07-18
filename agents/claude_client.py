"""
Thin wrapper around the Anthropic API shared by every agent.
Keeping one client + one call pattern makes it easy to swap models,
add logging, or add retries in a single place.
"""
import json
import os
import re

import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$")


def parse_json_array(text: str):
    """Parses a JSON array from model output, tolerating markdown code
    fences the model may wrap the JSON in despite being told not to.
    Returns None on any parse failure so callers can route to escalation."""
    stripped = _FENCE_RE.sub("", text.strip())
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def call_claude(system_prompt: str, user_content: str, max_tokens: int = 1000) -> str:
    """Single-turn call. Returns the text of the first content block.

    Every agent should call this with a narrow, single-purpose system
    prompt (extraction, policy-check, or draft) rather than one shared
    mega-prompt — keeps each agent's output inspectable and testable
    on its own.
    """
    response = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
