"""Tests for the anonymization utilities."""

from opendemocracy.input.anonymizer import anonymize_id, strip_pii


class TestStripPii:
    def test_strips_email(self) -> None:
        assert "[EMAIL]" in strip_pii("Contact me at alice@example.com for details")

    def test_strips_url(self) -> None:
        assert "[URL]" in strip_pii("Check https://example.com/profile for info")

    def test_strips_phone(self) -> None:
        result = strip_pii("Call me at 555-123-4567")
        assert "555-123-4567" not in result
        assert "[PHONE]" in result

    def test_strips_username(self) -> None:
        assert "[USER]" in strip_pii("As @johndoe said in the thread")

    def test_preserves_normal_text(self) -> None:
        text = "I support universal basic income for economic reasons"
        assert strip_pii(text) == text

    def test_strips_multiple_pii_types(self) -> None:
        text = "Email alice@test.com or call 555-000-1234 or visit https://t.co/abc"
        result = strip_pii(text)
        assert "alice@test.com" not in result
        assert "555-000-1234" not in result
        assert "https://t.co/abc" not in result


class TestAnonymizeId:
    def test_deterministic(self) -> None:
        assert anonymize_id("user123", "salt") == anonymize_id("user123", "salt")

    def test_different_salt_different_hash(self) -> None:
        assert anonymize_id("user123", "a") != anonymize_id("user123", "b")

    def test_different_ids_different_hash(self) -> None:
        assert anonymize_id("user1", "salt") != anonymize_id("user2", "salt")

    def test_returns_hex_string(self) -> None:
        result = anonymize_id("test")
        assert len(result) == 16
        int(result, 16)  # should not raise
