"""Tests for the multi-factor enrollment protocol."""

import pytest

from opendemocracy.identity.biometrics import create_template
from opendemocracy.identity.enrollment import enroll
from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import BiometricFactor


def _fingerprint() -> object:
    return create_template(b"finger_data", BiometricFactor.FINGERPRINT, 0.9)


def _face() -> object:
    return create_template(b"face_data", BiometricFactor.FACE, 0.85)


def _iris() -> object:
    return create_template(b"iris_data", BiometricFactor.IRIS, 0.92)


class TestEnroll:
    def test_successful_enrollment(self) -> None:
        reg = IdentityRegistry()
        record = enroll([_fingerprint(), _face()], reg)  # type: ignore[arg-type]
        assert record.public_key != ""
        assert BiometricFactor.FINGERPRINT in record.factors_enrolled
        assert BiometricFactor.FACE in record.factors_enrolled
        assert reg.count == 1

    def test_enrollment_with_three_factors(self) -> None:
        reg = IdentityRegistry()
        record = enroll([_fingerprint(), _face(), _iris()], reg)  # type: ignore[arg-type]
        assert len(record.factors_enrolled) == 3

    def test_rejects_single_factor(self) -> None:
        reg = IdentityRegistry()
        with pytest.raises(ValueError, match="At least"):
            enroll([_fingerprint()], reg)  # type: ignore[arg-type]

    def test_rejects_duplicate_factors(self) -> None:
        reg = IdentityRegistry()
        with pytest.raises(ValueError, match="Duplicate"):
            enroll([_fingerprint(), _fingerprint()], reg)  # type: ignore[arg-type]

    def test_registry_populated_after_enrollment(self) -> None:
        reg = IdentityRegistry()
        record = enroll([_fingerprint(), _face()], reg)  # type: ignore[arg-type]
        assert reg.is_enrolled(record.anonymous_id)
        assert reg.lookup(record.anonymous_id) is record
