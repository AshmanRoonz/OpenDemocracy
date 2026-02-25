"""Anonymization utilities for stripping PII from collected opinions."""

from __future__ import annotations

import hashlib
import re


# Patterns for common PII
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_URL_RE = re.compile(r"https?://\S+")
_PHONE_RE = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")
_USERNAME_RE = re.compile(r"@\w{1,30}")
_SUBREDDIT_SELF_RE = re.compile(r"\b[Ii]\s+am\s+u/\w+")


def strip_pii(text: str) -> str:
    """Remove personally-identifiable information from text.

    Strips emails, URLs, phone numbers, @-mentions, and self-identification
    patterns. This is a first-pass filter — not a substitute for manual review
    on sensitive datasets.
    """
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _URL_RE.sub("[URL]", text)
    text = _PHONE_RE.sub("[PHONE]", text)
    text = _USERNAME_RE.sub("[USER]", text)
    text = _SUBREDDIT_SELF_RE.sub("[SELF-ID]", text)
    return text


def anonymize_id(raw_id: str, salt: str = "") -> str:
    """One-way hash an identifier so it can't be reversed to the original.

    Uses SHA-256 with an optional salt. The same (raw_id, salt) pair always
    produces the same hash, enabling deduplication without storing raw IDs.
    """
    payload = f"{salt}:{raw_id}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]
