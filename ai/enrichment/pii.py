"""Redacts obvious PII from review text before it ever reaches the LLM
provider. Deliberately regex-based, not a NER model or a third-party PII
service: at review-comment length and volume, a handful of well-tested
patterns (email, phone, credit card) catch the cases that actually show up
in free-text reviews, with zero added infrastructure or latency. See
ADR-007's stance on not adding tooling weight this project's scale doesn't
need, and docs/architecture/04-ai-architecture.md.

Not a general PII/PHI compliance solution: it does not catch names,
addresses, or context-dependent identifiers, which would need an NER model
to reliably find. It exists to stop the clearest, highest-confidence leaks
(an email or phone number pasted into a review) from ever leaving this
system in an LLM prompt.
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[ -]?)?(?:\(\d{2,4}\)[ -]?)?\d{3,4}[ -]?\d{3,4}[ -]?\d{0,4}\b")


def scrub_pii(text: str) -> tuple[str, int]:
    """Returns (scrubbed_text, redaction_count). Order matters: credit card
    numbers are checked before the looser phone pattern, since a 16-digit
    card number would otherwise also match the phone regex and get labeled
    wrong. Redaction count is stored for traceability (ENRICHMENT_LOG,
    REVIEW_ENRICHED) so a spike in redactions is visible without re-reading
    every raw comment."""
    if not text:
        return text, 0

    count = 0

    def _redact(pattern: re.Pattern, label: str, value: str) -> str:
        nonlocal count

        def _sub(match: re.Match) -> str:
            nonlocal count
            count += 1
            return label

        return pattern.sub(_sub, value)

    scrubbed = _redact(_EMAIL_RE, "[REDACTED_EMAIL]", text)
    scrubbed = _redact(_CREDIT_CARD_RE, "[REDACTED_CARD]", scrubbed)
    scrubbed = _redact(_PHONE_RE, "[REDACTED_PHONE]", scrubbed)
    return scrubbed, count


__all__ = ["scrub_pii"]
