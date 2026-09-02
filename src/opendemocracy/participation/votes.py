"""Standing, revocable votes with change history — the heart of *Vote*.

An election records a vote once and freezes it. Vote does the opposite: a vote
*stands* until its owner changes or withdraws it. That single property turns
public opinion from a snapshot into a living curve, and it makes the most
valuable data in the system visible — **minds changing**. When someone changes
their vote, Vote asks what changed it, so arguments are measured by who they
actually moved rather than by applause.

Design rules, all enforced here:

* **One person, one standing vote per topic.** Changing it replaces the old
  stance; it never adds a second one.
* **Every change is appended, never overwritten.** The ledger is the full
  history; the current tally is derived from it. Nothing is ever deleted.
* **Tallies are deterministic and replayable.** A tally at any moment is a
  pure function of the ledger up to that moment, so anyone can rerun it and
  get the same numbers. No model is involved in producing a figure.
* **The denominator is always part of the result.** A tally reports how many
  people currently stand behind each option *and* how many ever took part, so
  a number can never be shown without the people behind it.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime

from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import VerificationResult
from opendemocracy.participation.relevance import _aware
from opendemocracy.participation.submissions import check_participant
from opendemocracy.participation.topics import TopicStore


def _now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class VoteEvent:
    """One append-only ledger entry: a vote cast, changed, or withdrawn.

    ``choice`` is ``None`` for a withdrawal. ``reason`` is the citizen's own
    answer to "what changed your mind?" — free text, optional, never inferred.
    """

    topic_id: str
    anonymous_voter_id: str
    previous: str | None
    choice: str | None
    reason: str | None = None
    at: datetime = field(default_factory=_now)

    @property
    def kind(self) -> str:
        if self.choice is None:
            return "withdrawn"
        return "cast" if self.previous is None else "changed"


@dataclass
class Tally:
    """Deterministic counts for one topic at one moment, denominator included."""

    topic_id: str
    at: datetime
    counts: dict[str, int]  # option -> people currently standing behind it
    standing: int  # people with a live vote right now
    ever_participated: int  # distinct people who have ever cast on this topic
    withdrawn: int  # people who cast and later withdrew (and haven't returned)
    changes: int  # vote changes so far (not counting first casts/withdrawals)

    def share(self, option: str) -> float:
        """Fraction of *standing* voters behind ``option`` (0 when nobody stands)."""
        if self.standing == 0:
            return 0.0
        return self.counts.get(option, 0) / self.standing


@dataclass
class Migration:
    """How many people moved from one stance to another, and what they said."""

    from_choice: str | None
    to_choice: str | None
    count: int
    reasons: list[str] = field(default_factory=list)


class StandingVoteLedger:
    """Append-only ledger of standing votes, with derived tallies and history."""

    def __init__(
        self, topic_store: TopicStore, identity_registry: IdentityRegistry
    ) -> None:
        self._topic_store = topic_store
        self._identity_registry = identity_registry
        self._events: list[VoteEvent] = []
        # (topic_id, voter_id) -> current choice (None once withdrawn)
        self._current: dict[tuple[str, str], str | None] = {}

    # -- writing ----------------------------------------------------------- #

    def cast(
        self,
        verification: VerificationResult,
        topic_id: str,
        choice: str,
        reason: str | None = None,
    ) -> VoteEvent:
        """Cast a vote, or change a standing one to ``choice``.

        Raises ``PermissionError`` for identity failures and ``ValueError`` if
        the topic is missing/closed/doesn't take votes, the choice isn't one
        of the topic's options, or the vote already stands at ``choice``.
        """
        topic = check_participant(
            verification, self._identity_registry, self._topic_store, topic_id
        )
        if not topic.allow_votes:
            raise ValueError(f"Topic {topic_id!r} does not accept votes")
        if topic.vote_options and choice not in topic.vote_options:
            raise ValueError(
                f"Invalid vote choice {choice!r}; options are: {topic.vote_options}"
            )

        key = (topic_id, verification.anonymous_id)
        previous = self._current.get(key)
        if previous == choice:
            raise ValueError(f"Vote already stands at {choice!r}")

        return self._append(key, previous, choice, reason)

    def withdraw(
        self,
        verification: VerificationResult,
        topic_id: str,
        reason: str | None = None,
    ) -> VoteEvent:
        """Withdraw a standing vote. The history of having voted remains."""
        check_participant(
            verification, self._identity_registry, self._topic_store, topic_id
        )
        key = (topic_id, verification.anonymous_id)
        previous = self._current.get(key)
        if previous is None:
            raise ValueError("No standing vote to withdraw")
        return self._append(key, previous, None, reason)

    def _append(
        self,
        key: tuple[str, str],
        previous: str | None,
        choice: str | None,
        reason: str | None,
    ) -> VoteEvent:
        event = VoteEvent(
            topic_id=key[0],
            anonymous_voter_id=key[1],
            previous=previous,
            choice=choice,
            reason=(reason or "").strip() or None,
        )
        self._events.append(event)
        self._current[key] = choice
        return event

    # -- reading ----------------------------------------------------------- #

    def current(self, topic_id: str, anonymous_voter_id: str) -> str | None:
        """The voter's standing choice on the topic, or ``None``."""
        return self._current.get((topic_id, anonymous_voter_id))

    def history(
        self, topic_id: str, anonymous_voter_id: str | None = None
    ) -> list[VoteEvent]:
        """Ledger entries for a topic, oldest first, optionally for one voter."""
        return [
            e
            for e in self._events
            if e.topic_id == topic_id
            and (
                anonymous_voter_id is None or e.anonymous_voter_id == anonymous_voter_id
            )
        ]

    def participant_count(self, topic_id: str) -> int:
        """Distinct people with a *standing* vote — the count quorum is measured in."""
        return self.tally(topic_id).standing

    def tally(self, topic_id: str, at: datetime | None = None) -> Tally:
        """Replay the ledger up to ``at`` (default: now) into a deterministic tally."""
        cutoff = _aware(at) if at is not None else None
        standing: dict[str, str | None] = {}
        ever: set[str] = set()
        changes = 0
        last_at: datetime | None = None
        for e in self._events:
            if e.topic_id != topic_id:
                continue
            if cutoff is not None and _aware(e.at) > cutoff:
                continue
            ever.add(e.anonymous_voter_id)
            if e.kind == "changed":
                changes += 1
            standing[e.anonymous_voter_id] = e.choice
            last_at = e.at

        counts: Counter[str] = Counter(c for c in standing.values() if c is not None)
        options = self._option_order(topic_id, counts)
        return Tally(
            topic_id=topic_id,
            at=cutoff or (last_at or _now()),
            counts={opt: counts.get(opt, 0) for opt in options},
            standing=sum(counts.values()),
            ever_participated=len(ever),
            withdrawn=sum(1 for c in standing.values() if c is None),
            changes=changes,
        )

    def timeline(self, topic_id: str) -> list[Tally]:
        """The living curve: one tally after every ledger event on the topic."""
        return [self.tally(topic_id, at=e.at) for e in self.history(topic_id)]

    def migrations(self, topic_id: str) -> list[Migration]:
        """Who moved where, and why — argument efficacy as vote migration.

        Ordered by how many people made each move, largest first, with ties in
        stable ledger order so results are reproducible.
        """
        buckets: dict[tuple[str | None, str | None], Migration] = {}
        for e in self.history(topic_id):
            if e.previous is None:
                continue  # a first cast is not a migration
            m = buckets.setdefault(
                (e.previous, e.choice), Migration(e.previous, e.choice, 0)
            )
            m.count += 1
            if e.reason:
                m.reasons.append(e.reason)
        return sorted(buckets.values(), key=lambda m: -m.count)

    def _option_order(self, topic_id: str, counts: Counter[str]) -> list[str]:
        topic = self._topic_store.get(topic_id)
        declared = list(topic.vote_options) if topic and topic.vote_options else []
        extra = sorted(c for c in counts if c not in declared)
        return declared + extra
