"""Tests for the server-side identity registry."""

import pytest

from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import BiometricFactor, EnrollmentRecord


def _make_record(**kwargs: object) -> EnrollmentRecord:
    defaults: dict[str, object] = {
        "anonymous_id": "abc123",
        "public_key": "pubkey_abc",
        "factors_enrolled": [BiometricFactor.FINGERPRINT, BiometricFactor.FACE],
    }
    defaults.update(kwargs)
    return EnrollmentRecord(**defaults)  # type: ignore[arg-type]


class TestIdentityRegistry:
    def test_register_and_lookup(self) -> None:
        reg = IdentityRegistry()
        record = _make_record()
        reg.register(record)
        assert reg.lookup("abc123") is record

    def test_lookup_missing_returns_none(self) -> None:
        reg = IdentityRegistry()
        assert reg.lookup("nonexistent") is None

    def test_lookup_by_public_key(self) -> None:
        reg = IdentityRegistry()
        record = _make_record()
        reg.register(record)
        assert reg.lookup_by_public_key("pubkey_abc") is record

    def test_duplicate_id_raises(self) -> None:
        reg = IdentityRegistry()
        reg.register(_make_record())
        with pytest.raises(RuntimeError, match="already registered"):
            reg.register(_make_record())

    def test_duplicate_pubkey_raises(self) -> None:
        reg = IdentityRegistry()
        reg.register(_make_record(anonymous_id="a1", public_key="same_key"))
        with pytest.raises(RuntimeError, match="already registered"):
            reg.register(_make_record(anonymous_id="a2", public_key="same_key"))

    def test_revoke(self) -> None:
        reg = IdentityRegistry()
        reg.register(_make_record())
        assert reg.is_enrolled("abc123") is True
        reg.revoke("abc123")
        assert reg.is_enrolled("abc123") is False

    def test_revoke_unknown_returns_false(self) -> None:
        reg = IdentityRegistry()
        assert reg.revoke("nobody") is False

    def test_count(self) -> None:
        reg = IdentityRegistry()
        assert reg.count == 0
        reg.register(_make_record(anonymous_id="a", public_key="k1"))
        reg.register(_make_record(anonymous_id="b", public_key="k2"))
        assert reg.count == 2

    def test_active_count_excludes_revoked(self) -> None:
        reg = IdentityRegistry()
        reg.register(_make_record(anonymous_id="a", public_key="k1"))
        reg.register(_make_record(anonymous_id="b", public_key="k2"))
        reg.revoke("a")
        assert reg.active_count == 1
