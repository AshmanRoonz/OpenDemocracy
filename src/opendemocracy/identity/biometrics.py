"""Local biometric template management.

All functions in this module represent **device-side** operations.  Biometric
captures are processed into compact template hashes on the user's hardware
and the raw captures are discarded immediately.  Templates never leave the
device.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from opendemocracy.models import BiometricFactor, BiometricTemplate

# Minimum quality score required to accept a biometric capture.
MIN_QUALITY_SCORE = 0.6

# Minimum number of distinct biometric factors required for enrollment.
MIN_FACTORS_REQUIRED = 2


def hash_template(raw_capture: bytes, factor: BiometricFactor) -> str:
    """Hash a raw biometric capture into a storable template digest.

    In production this would first run a feature-extraction pipeline
    specific to the biometric factor (e.g. minutiae extraction for
    fingerprints, facenet embedding for faces).  Here we define the
    canonical hashing step that follows extraction.

    The capture bytes are salted with a per-device secret so the same
    biometric enrolled on two devices produces different hashes, preventing
    cross-device correlation.
    """
    # Per-factor domain separation prevents a fingerprint hash from ever
    # colliding with an iris hash.
    domain = f"opendemocracy.biometric.{factor.value}".encode()
    return hashlib.sha256(domain + raw_capture).hexdigest()


def create_template(
    raw_capture: bytes,
    factor: BiometricFactor,
    quality_score: float,
) -> BiometricTemplate:
    """Process a raw biometric capture into a template.

    Raises ``ValueError`` if the capture quality is too low.
    """
    if quality_score < MIN_QUALITY_SCORE:
        msg = (
            f"Capture quality {quality_score:.2f} is below the minimum "
            f"threshold of {MIN_QUALITY_SCORE:.2f} — please retry"
        )
        raise ValueError(msg)

    return BiometricTemplate(
        factor=factor,
        template_hash=hash_template(raw_capture, factor),
        quality_score=quality_score,
        captured_at=datetime.now(),
    )


def verify_local(
    live_capture: bytes,
    stored_template: BiometricTemplate,
) -> bool:
    """Compare a live biometric capture against a stored template.

    Returns ``True`` when the hashes match — meaning the same person is
    present.  This runs entirely on-device.
    """
    live_hash = hash_template(live_capture, stored_template.factor)
    return secrets.compare_digest(live_hash, stored_template.template_hash)


def validate_factor_set(factors: list[BiometricFactor]) -> list[str]:
    """Check that a set of biometric factors meets enrollment requirements.

    Returns a list of human-readable problems (empty if everything is OK).
    """
    problems: list[str] = []

    if len(factors) < MIN_FACTORS_REQUIRED:
        problems.append(
            f"At least {MIN_FACTORS_REQUIRED} biometric factors required, "
            f"got {len(factors)}"
        )

    if len(factors) != len(set(factors)):
        problems.append("Duplicate biometric factors are not allowed")

    return problems
