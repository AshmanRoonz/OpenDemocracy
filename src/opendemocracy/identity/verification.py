"""Challenge-response biometric verification protocol.

Verification proves that the person who originally enrolled is currently
present — without any biometric data leaving the device.

Protocol
--------
1. Participant requests access.
2. Server issues a random **challenge** (nonce + expiry).
3. Participant authenticates locally via biometrics (device-side).
4. On success the device **signs** the nonce with the private key.
5. The signed response is sent to the server.
6. The server **verifies** the signature against the stored public key.
7. On success the server returns a ``VerificationResult`` authorizing the
   participant for a specific action (e.g. submitting a vote).
"""

from __future__ import annotations

from datetime import UTC, datetime

from opendemocracy.identity.crypto import generate_nonce, verify_signature
from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import AuthChallenge, VerificationResult


def issue_challenge(expires_seconds: int = 300) -> AuthChallenge:
    """Create a new challenge for a participant to sign.

    The challenge contains a cryptographically random nonce and an expiry
    window (default 5 minutes).
    """
    return AuthChallenge(
        nonce=generate_nonce(),
        expires_seconds=expires_seconds,
    )


def _challenge_expired(challenge: AuthChallenge) -> bool:
    """Check whether a challenge has exceeded its time window."""
    elapsed = (
        datetime.now(tz=UTC) - challenge.issued_at.replace(tzinfo=UTC)
    ).total_seconds()
    return elapsed > challenge.expires_seconds


def verify(
    challenge: AuthChallenge,
    signature: str,
    anonymous_id: str,
    registry: IdentityRegistry,
) -> VerificationResult:
    """Verify a signed challenge response from a participant.

    Parameters
    ----------
    challenge:
        The challenge originally issued by ``issue_challenge``.
    signature:
        The device-produced signature over the challenge nonce.
    anonymous_id:
        The participant's anonymous ID (from enrollment).
    registry:
        The server-side identity registry.

    Returns
    -------
    VerificationResult
        Contains ``verified=True`` if the signature is valid and the
        participant is who they claim to be.
    """
    # Guard: already used.
    if challenge.consumed:
        return VerificationResult(
            verified=False,
            anonymous_id=anonymous_id,
            reason="Challenge has already been consumed",
        )

    # Guard: expired.
    if _challenge_expired(challenge):
        return VerificationResult(
            verified=False,
            anonymous_id=anonymous_id,
            reason="Challenge has expired",
        )

    # Look up the enrollment record.
    record = registry.lookup(anonymous_id)
    if record is None:
        return VerificationResult(
            verified=False,
            anonymous_id=anonymous_id,
            reason="Unknown participant ID",
        )

    if record.revoked:
        return VerificationResult(
            verified=False,
            anonymous_id=anonymous_id,
            reason="Enrollment has been revoked",
        )

    # Verify the cryptographic signature.
    if not verify_signature(record.public_key, challenge.nonce, signature):
        return VerificationResult(
            verified=False,
            anonymous_id=anonymous_id,
            reason="Invalid signature",
        )

    # Mark the challenge as consumed so it can't be replayed.
    challenge.consumed = True

    return VerificationResult(
        verified=True,
        anonymous_id=anonymous_id,
        factors_verified=list(record.factors_enrolled),
        verified_at=datetime.now(tz=UTC),
    )
