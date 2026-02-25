"""Tests for cryptographic operations."""

from opendemocracy.identity.crypto import (
    generate_keypair,
    generate_nonce,
    sign_challenge,
    verify_signature,
)


class TestGenerateKeypair:
    def test_returns_two_hex_strings(self) -> None:
        private, public = generate_keypair()
        assert len(private) == 64  # 32 bytes hex
        assert len(public) == 64  # SHA-256 hex
        int(private, 16)
        int(public, 16)

    def test_each_call_produces_unique_keys(self) -> None:
        k1 = generate_keypair()
        k2 = generate_keypair()
        assert k1[0] != k2[0]
        assert k1[1] != k2[1]


class TestGenerateNonce:
    def test_returns_hex_string(self) -> None:
        nonce = generate_nonce()
        assert len(nonce) == 64  # 32 bytes hex
        int(nonce, 16)

    def test_nonces_are_unique(self) -> None:
        n1 = generate_nonce()
        n2 = generate_nonce()
        assert n1 != n2


class TestSignAndVerify:
    def test_signature_matches_public_key(self) -> None:
        """Sign with public key, verify with public key — protocol demo."""
        _private, public = generate_keypair()
        nonce = generate_nonce()
        # In the prototype both sides sign with the public key.
        signature = sign_challenge(public, nonce)
        assert verify_signature(public, nonce, signature) is True

    def test_wrong_key_fails_verification(self) -> None:
        _priv1, pub1 = generate_keypair()
        _priv2, pub2 = generate_keypair()
        nonce = generate_nonce()
        signature = sign_challenge(pub1, nonce)
        assert verify_signature(pub2, nonce, signature) is False

    def test_tampered_nonce_fails_verification(self) -> None:
        _private, public = generate_keypair()
        nonce = generate_nonce()
        signature = sign_challenge(public, nonce)
        assert verify_signature(public, "tampered_nonce", signature) is False
