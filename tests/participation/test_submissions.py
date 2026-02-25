"""Tests for the verified submission system."""

import pytest

from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import (
    BiometricFactor,
    EnrollmentRecord,
    SubmissionType,
    Topic,
    VerificationResult,
)
from opendemocracy.participation.submissions import SubmissionStore
from opendemocracy.participation.topics import TopicStore


def _make_registry_and_voter() -> tuple[IdentityRegistry, str]:
    reg = IdentityRegistry()
    record = EnrollmentRecord(
        anonymous_id="voter_1",
        public_key="pubkey_1",
        factors_enrolled=[BiometricFactor.FINGERPRINT, BiometricFactor.FACE],
    )
    reg.register(record)
    return reg, "voter_1"


def _ok_verification(anonymous_id: str = "voter_1") -> VerificationResult:
    return VerificationResult(
        verified=True,
        anonymous_id=anonymous_id,
        factors_verified=[BiometricFactor.FINGERPRINT, BiometricFactor.FACE],
    )


def _failed_verification() -> VerificationResult:
    return VerificationResult(verified=False, reason="test failure")


def _make_topic(**kwargs: object) -> Topic:
    defaults: dict[str, object] = {
        "id": "topic_1",
        "title": "Universal Basic Income",
        "description": "Should we implement UBI?",
        "allow_opinions": True,
        "allow_ideas": True,
        "allow_votes": True,
        "vote_options": ["Yes", "No", "Undecided"],
    }
    defaults.update(kwargs)
    return Topic(**defaults)  # type: ignore[arg-type]


class TestSubmissionStore:
    def test_submit_opinion(self) -> None:
        reg, voter_id = _make_registry_and_voter()
        topics = TopicStore()
        topics.create(_make_topic())
        store = SubmissionStore(topics, reg)

        sub = store.submit(
            _ok_verification(voter_id),
            "topic_1",
            SubmissionType.OPINION,
            "I think UBI would reduce poverty",
        )
        assert sub.anonymous_voter_id == voter_id
        assert sub.submission_type == SubmissionType.OPINION
        assert store.total_count == 1

    def test_submit_idea(self) -> None:
        reg, voter_id = _make_registry_and_voter()
        topics = TopicStore()
        topics.create(_make_topic())
        store = SubmissionStore(topics, reg)

        sub = store.submit(
            _ok_verification(voter_id),
            "topic_1",
            SubmissionType.IDEA,
            "Phase in UBI starting with low-income areas",
        )
        assert sub.submission_type == SubmissionType.IDEA

    def test_submit_vote(self) -> None:
        reg, voter_id = _make_registry_and_voter()
        topics = TopicStore()
        topics.create(_make_topic())
        store = SubmissionStore(topics, reg)

        sub = store.submit(
            _ok_verification(voter_id),
            "topic_1",
            SubmissionType.VOTE,
            "Yes",
        )
        assert sub.content == "Yes"

    def test_invalid_vote_option_rejected(self) -> None:
        reg, voter_id = _make_registry_and_voter()
        topics = TopicStore()
        topics.create(_make_topic())
        store = SubmissionStore(topics, reg)

        with pytest.raises(ValueError, match="Invalid vote choice"):
            store.submit(
                _ok_verification(voter_id),
                "topic_1",
                SubmissionType.VOTE,
                "Maybe",
            )

    def test_duplicate_submission_blocked(self) -> None:
        reg, voter_id = _make_registry_and_voter()
        topics = TopicStore()
        topics.create(_make_topic())
        store = SubmissionStore(topics, reg)

        store.submit(
            _ok_verification(voter_id),
            "topic_1",
            SubmissionType.VOTE,
            "Yes",
        )
        with pytest.raises(ValueError, match="already submitted"):
            store.submit(
                _ok_verification(voter_id),
                "topic_1",
                SubmissionType.VOTE,
                "No",
            )

    def test_same_person_can_submit_different_types(self) -> None:
        """One person can submit an opinion AND vote on the same topic."""
        reg, voter_id = _make_registry_and_voter()
        topics = TopicStore()
        topics.create(_make_topic())
        store = SubmissionStore(topics, reg)

        store.submit(
            _ok_verification(voter_id),
            "topic_1",
            SubmissionType.OPINION,
            "My thoughts on UBI",
        )
        store.submit(
            _ok_verification(voter_id),
            "topic_1",
            SubmissionType.VOTE,
            "Yes",
        )
        assert store.total_count == 2

    def test_failed_verification_blocked(self) -> None:
        reg, _voter_id = _make_registry_and_voter()
        topics = TopicStore()
        topics.create(_make_topic())
        store = SubmissionStore(topics, reg)

        with pytest.raises(PermissionError, match="verification failed"):
            store.submit(
                _failed_verification(),
                "topic_1",
                SubmissionType.OPINION,
                "Trying to sneak in",
            )

    def test_nonexistent_topic_rejected(self) -> None:
        reg, voter_id = _make_registry_and_voter()
        topics = TopicStore()
        store = SubmissionStore(topics, reg)

        with pytest.raises(ValueError, match="does not exist"):
            store.submit(
                _ok_verification(voter_id),
                "no_such_topic",
                SubmissionType.OPINION,
                "Hello",
            )

    def test_has_submitted(self) -> None:
        reg, voter_id = _make_registry_and_voter()
        topics = TopicStore()
        topics.create(_make_topic())
        store = SubmissionStore(topics, reg)

        assert store.has_submitted(voter_id, "topic_1", SubmissionType.VOTE) is False
        store.submit(
            _ok_verification(voter_id), "topic_1", SubmissionType.VOTE, "Yes"
        )
        assert store.has_submitted(voter_id, "topic_1", SubmissionType.VOTE) is True

    def test_get_submissions_by_topic(self) -> None:
        reg = IdentityRegistry()
        for i in range(3):
            reg.register(EnrollmentRecord(
                anonymous_id=f"v{i}",
                public_key=f"pk{i}",
                factors_enrolled=[BiometricFactor.FINGERPRINT, BiometricFactor.FACE],
            ))

        topics = TopicStore()
        topics.create(_make_topic())
        store = SubmissionStore(topics, reg)

        for i in range(3):
            store.submit(
                _ok_verification(f"v{i}"),
                "topic_1",
                SubmissionType.VOTE,
                "Yes" if i < 2 else "No",
            )

        results = store.get_submissions("topic_1", SubmissionType.VOTE)
        assert len(results) == 3

    def test_disabled_submission_type_rejected(self) -> None:
        reg, voter_id = _make_registry_and_voter()
        topics = TopicStore()
        topics.create(_make_topic(allow_ideas=False))
        store = SubmissionStore(topics, reg)

        with pytest.raises(ValueError, match="does not accept"):
            store.submit(
                _ok_verification(voter_id),
                "topic_1",
                SubmissionType.IDEA,
                "My idea",
            )
