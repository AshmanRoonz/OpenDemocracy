"""Tests for the challenge-response verification protocol."""

from opendemocracy.identity.crypto import generate_keypair, sign_challenge
from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.identity.verification import issue_challenge, verify
from opendemocracy.models import BiometricFactor, EnrollmentRecord


def _setup_enrolled() -> tuple[IdentityRegistry, EnrollmentRecord, str]:
    """Create a registry with one enrolled participant, return (reg, record, pubkey)."""
    _private, public = generate_keypair()
    reg = IdentityRegistry()
    record = EnrollmentRecord(
        anonymous_id="voter_1",
        public_key=public,
        factors_enrolled=[BiometricFactor.FINGERPRINT, BiometricFactor.FACE],
    )
    reg.register(record)
    return reg, record, public


class TestIssueChallenge:
    def test_challenge_has_nonce(self) -> None:
        ch = issue_challenge()
        assert len(ch.nonce) > 0
        assert ch.consumed is False

    def test_custom_expiry(self) -> None:
        ch = issue_challenge(expires_seconds=60)
        assert ch.expires_seconds == 60


class TestVerify:
    def test_valid_verification(self) -> None:
        reg, record, pubkey = _setup_enrolled()
        ch = issue_challenge()
        # Device signs with public key (prototype protocol).
        sig = sign_challenge(pubkey, ch.nonce)
        result = verify(ch, sig, "voter_1", reg)
        assert result.verified is True
        assert result.anonymous_id == "voter_1"
        assert BiometricFactor.FINGERPRINT in result.factors_verified

    def test_wrong_signature_fails(self) -> None:
        reg, _record, _pubkey = _setup_enrolled()
        ch = issue_challenge()
        result = verify(ch, "bad_signature", "voter_1", reg)
        assert result.verified is False
        assert "Invalid signature" in result.reason

    def test_unknown_participant_fails(self) -> None:
        reg, _record, _pubkey = _setup_enrolled()
        ch = issue_challenge()
        result = verify(ch, "any_sig", "unknown_id", reg)
        assert result.verified is False
        assert "Unknown" in result.reason

    def test_consumed_challenge_fails(self) -> None:
        reg, _record, pubkey = _setup_enrolled()
        ch = issue_challenge()
        sig = sign_challenge(pubkey, ch.nonce)
        # First verify succeeds.
        verify(ch, sig, "voter_1", reg)
        # Second attempt with same challenge fails.
        result = verify(ch, sig, "voter_1", reg)
        assert result.verified is False
        assert "consumed" in result.reason

    def test_revoked_participant_fails(self) -> None:
        reg, _record, pubkey = _setup_enrolled()
        reg.revoke("voter_1")
        ch = issue_challenge()
        sig = sign_challenge(pubkey, ch.nonce)
        result = verify(ch, sig, "voter_1", reg)
        assert result.verified is False
        assert "revoked" in result.reason
