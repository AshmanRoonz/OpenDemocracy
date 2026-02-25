"""Verified submission of opinions, ideas, and votes.

Every submission flows through the same path:

1. Participant authenticates via biometric challenge-response.
2. The ``VerificationResult`` proves they are enrolled and present.
3. The system checks they haven't already submitted on this topic.
4. The submission is recorded and linked to their anonymous ID.

No personal information is stored — only the anonymous voter ID, the
topic, and the content of the submission.
"""

from __future__ import annotations

from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import Submission, SubmissionType, VerificationResult
from opendemocracy.participation.topics import TopicStore


class SubmissionStore:
    """Manages verified submissions with one-person-one-submission enforcement."""

    def __init__(
        self,
        topic_store: TopicStore,
        identity_registry: IdentityRegistry,
    ) -> None:
        self._topic_store = topic_store
        self._identity_registry = identity_registry
        self._submissions: list[Submission] = []
        # (topic_id, anonymous_voter_id, submission_type) → True
        self._submitted: set[tuple[str, str, str]] = set()

    def submit(
        self,
        verification: VerificationResult,
        topic_id: str,
        submission_type: SubmissionType,
        content: str,
    ) -> Submission:
        """Record a verified submission.

        Parameters
        ----------
        verification:
            A successful ``VerificationResult`` from the identity layer.
        topic_id:
            The topic this submission is for.
        submission_type:
            OPINION, IDEA, or VOTE.
        content:
            Free text for opinions/ideas, or the chosen option for votes.

        Returns
        -------
        Submission
            The recorded submission.

        Raises
        ------
        PermissionError
            If the verification failed or the participant is not enrolled.
        ValueError
            If the topic doesn't exist, is closed, or the participant has
            already submitted this type on this topic.
        """
        # Must be verified.
        if not verification.verified:
            raise PermissionError(
                f"Identity verification failed: {verification.reason}"
            )

        # Must be enrolled and active.
        if not self._identity_registry.is_enrolled(verification.anonymous_id):
            raise PermissionError("Participant is not enrolled or was revoked")

        # Topic must exist and be open.
        topic = self._topic_store.get(topic_id)
        if topic is None:
            raise ValueError(f"Topic {topic_id!r} does not exist")

        if not self._topic_store.is_open(topic_id):
            raise ValueError(f"Topic {topic_id!r} is closed for submissions")

        # Check topic allows this submission type.
        type_allowed = {
            SubmissionType.OPINION: topic.allow_opinions,
            SubmissionType.IDEA: topic.allow_ideas,
            SubmissionType.VOTE: topic.allow_votes,
        }
        if not type_allowed.get(submission_type, False):
            raise ValueError(
                f"Topic {topic_id!r} does not accept "
                f"{submission_type.value} submissions"
            )

        # For votes, validate the choice is one of the allowed options.
        if (
            submission_type == SubmissionType.VOTE
            and topic.vote_options
            and content not in topic.vote_options
        ):
            raise ValueError(
                f"Invalid vote choice {content!r}; options are: {topic.vote_options}"
            )

        # One person, one submission per type per topic.
        dedup_key = (topic_id, verification.anonymous_id, submission_type.value)
        if dedup_key in self._submitted:
            raise ValueError(
                f"Participant has already submitted a {submission_type.value} "
                f"on topic {topic_id!r}"
            )

        submission = Submission(
            topic_id=topic_id,
            anonymous_voter_id=verification.anonymous_id,
            submission_type=submission_type,
            content=content,
        )
        self._submissions.append(submission)
        self._submitted.add(dedup_key)
        return submission

    def get_submissions(
        self,
        topic_id: str,
        submission_type: SubmissionType | None = None,
    ) -> list[Submission]:
        """Retrieve all submissions for a topic, optionally filtered by type."""
        results = [s for s in self._submissions if s.topic_id == topic_id]
        if submission_type is not None:
            results = [s for s in results if s.submission_type == submission_type]
        return results

    def has_submitted(
        self,
        anonymous_id: str,
        topic_id: str,
        submission_type: SubmissionType,
    ) -> bool:
        """Check if a participant has already submitted on a topic."""
        return (topic_id, anonymous_id, submission_type.value) in self._submitted

    @property
    def total_count(self) -> int:
        """Total number of submissions across all topics."""
        return len(self._submissions)
