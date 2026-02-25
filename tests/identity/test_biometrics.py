"""Tests for local biometric template management."""

import pytest

from opendemocracy.identity.biometrics import (
    MIN_QUALITY_SCORE,
    create_template,
    hash_template,
    validate_factor_set,
    verify_local,
)
from opendemocracy.models import BiometricFactor


class TestHashTemplate:
    def test_deterministic(self) -> None:
        h1 = hash_template(b"capture_data", BiometricFactor.FINGERPRINT)
        h2 = hash_template(b"capture_data", BiometricFactor.FINGERPRINT)
        assert h1 == h2

    def test_different_captures_different_hashes(self) -> None:
        h1 = hash_template(b"finger_1", BiometricFactor.FINGERPRINT)
        h2 = hash_template(b"finger_2", BiometricFactor.FINGERPRINT)
        assert h1 != h2

    def test_different_factors_different_hashes(self) -> None:
        """Same raw bytes but different factor types must produce different hashes."""
        h1 = hash_template(b"same_data", BiometricFactor.FINGERPRINT)
        h2 = hash_template(b"same_data", BiometricFactor.IRIS)
        assert h1 != h2

    def test_returns_hex_string(self) -> None:
        h = hash_template(b"data", BiometricFactor.FACE)
        assert len(h) == 64  # SHA-256 hex digest
        int(h, 16)  # should not raise


class TestCreateTemplate:
    def test_creates_valid_template(self) -> None:
        t = create_template(b"good_capture", BiometricFactor.IRIS, 0.9)
        assert t.factor == BiometricFactor.IRIS
        assert t.quality_score == 0.9
        assert len(t.template_hash) == 64

    def test_rejects_low_quality(self) -> None:
        with pytest.raises(ValueError, match="below the minimum"):
            create_template(b"blurry", BiometricFactor.FACE, 0.3)

    def test_accepts_exact_threshold(self) -> None:
        t = create_template(b"ok_capture", BiometricFactor.VOICE, MIN_QUALITY_SCORE)
        assert t.quality_score == MIN_QUALITY_SCORE


class TestVerifyLocal:
    def test_matching_capture_returns_true(self) -> None:
        t = create_template(b"my_finger", BiometricFactor.FINGERPRINT, 0.95)
        assert verify_local(b"my_finger", t) is True

    def test_different_capture_returns_false(self) -> None:
        t = create_template(b"my_finger", BiometricFactor.FINGERPRINT, 0.95)
        assert verify_local(b"someone_else", t) is False


class TestValidateFactorSet:
    def test_valid_multi_factor(self) -> None:
        problems = validate_factor_set(
            [BiometricFactor.FINGERPRINT, BiometricFactor.FACE]
        )
        assert problems == []

    def test_too_few_factors(self) -> None:
        problems = validate_factor_set([BiometricFactor.FINGERPRINT])
        assert len(problems) == 1
        assert "At least" in problems[0]

    def test_duplicate_factors(self) -> None:
        problems = validate_factor_set(
            [BiometricFactor.FACE, BiometricFactor.FACE]
        )
        assert any("Duplicate" in p for p in problems)

    def test_four_factors_valid(self) -> None:
        problems = validate_factor_set([
            BiometricFactor.FINGERPRINT,
            BiometricFactor.FACE,
            BiometricFactor.IRIS,
            BiometricFactor.VOICE,
        ])
        assert problems == []
