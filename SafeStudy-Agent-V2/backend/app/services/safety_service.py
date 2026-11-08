"""Safety engine: input screening + output validation.

Local rules always run. If ENKRYPT_API_KEY is set, Enkrypt AI Guardrails is
consulted as an additional check on output; any failure falls back to local rules.
"""
import re
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass
class SafetyResult:
    is_safe: bool
    reason: str


_INPUT_RULES = [
    (r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)", "Prompt-injection attempt"),
    (r"(reveal|show|print).{0,30}(system prompt|hidden instructions)", "System-prompt extraction attempt"),
    (r"\b(bypass|disable|turn off)\b.{0,30}\b(safety|guardrails?|filters?)\b", "Safety bypass attempt"),
    (r"\b(cheat|cheating)\b.{0,30}\b(exam|test|quiz)\b", "Academic-integrity violation"),
    (r"\b(steal|leak)\b.{0,20}\b(answers?|answer key|question paper)\b", "Academic-integrity violation"),
    (r"\bhack the exam\b|\bgenerate (the )?answer key\b", "Academic-integrity violation"),
]
_OUTPUT_BLOCK = [
    "ignore previous instructions", "system prompt", "hack the exam",
    "steal answers", "generate answer key",
]

REFUSAL = (
    "I can help you understand the course material, but I can't help bypass academic rules "
    "or safety instructions. Ask me to explain the topic or give you a practice question instead."
)
UNVERIFIED = (
    "That response couldn't be verified as safe for students. "
    "Please check your course material or instructor."
)


def check_input(text: str) -> SafetyResult:
    low = text.lower()
    for pattern, reason in _INPUT_RULES:
        if re.search(pattern, low):
            return SafetyResult(False, reason)
    return SafetyResult(True, "Input passed local checks")


def _local_output(text: str) -> SafetyResult:
    low = text.lower()
    for phrase in _OUTPUT_BLOCK:
        if phrase in low:
            return SafetyResult(False, f"Output contained blocked phrase: {phrase}")
    return SafetyResult(True, "Approved by local safety rules")


def check_output(text: str) -> SafetyResult:
    local = _local_output(text)
    if not local.is_safe:
        return local
    key = get_settings().enkrypt_api_key
    if not key:
        return local
    try:
        r = httpx.post(
            "https://api.enkryptai.com/guardrails/detect",
            headers={"apikey": key},
            json={"text": text, "detectors": {
                "toxicity": {"enabled": True}, "nsfw": {"enabled": True},
                "injection_attack": {"enabled": True}, "policy_violation": {"enabled": True}}},
            timeout=8,
        )
        r.raise_for_status()
        summary = r.json().get("summary", {})
        flagged = [k for k, v in summary.items() if v and v != 0]
        if flagged:
            return SafetyResult(False, f"Enkrypt AI flagged: {', '.join(flagged)}")
        return SafetyResult(True, "Approved by Enkrypt AI Guardrails")
    except Exception:
        return local
