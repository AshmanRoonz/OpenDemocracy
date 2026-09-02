"""Tests for standing, revocable votes with change history."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import (
    BiometricFactor,
    EnrollmentRecord,
    Topic,
    VerificationResult,
)
from opendemocracy.participation.topics import TopicStore
from opendemocracy.participation.votes import StandingVoteLedger


def _setup(
    voters: int = 3, **topic_kwargs: object
) -> tuple[StandingVoteLedger, list[str]]:
    reg = IdentityRegistry()
    ids = []
    for i in range(voters):
        vid = f"voter_{i}"
        reg.register(
            EnrollmentRecord(
                anonymous_id=vid,
                public_key=f"pk_{i}",
                factors_enrolled=[BiometricFactor.FINGERPRINT, BiometricFactor.FACE],
            )
        )
        ids.append(vid)
    topics = TopicStore()
    defaults: dict[str, object] = {
        "id": "t1",
        "title": "Expand transit",
        "vote_options": ["Yes", "No"],
    }
    defaults.update(topic_kwargs)
    topics.create(Topic(**defaults))  # type: ignore[arg-type]
    return StandingVoteLedger(topics, reg), ids


def _v(vid: str, ok: bool = True) -> VerificationResult:
    return VerificationResult(
        verified=ok, anonymous_id=vid, reason="" if ok else "nope"
    )


# --------------------------------------------------------------------------- #
# Casting, changing, withdrawing                                              #
# --------------------------------------------------------------------------- #


def test_first_cast_is_recorded_as_cast() -> None:
    ledger, (a, *_) = _setup()
    e = ledger.cast(_v(a), "t1", "Yes")
    assert e.kind == "cast"
    assert e.previous is None
    assert ledger.current("t1", a) == "Yes"


def test_changing_replaces_rather_than_adds() -> None:
    ledger, (a, *_) = _setup()
    ledger.cast(_v(a), "t1", "Yes")
    e = ledger.cast(_v(a), "t1", "No", reason="The cost report changed my view")
    assert e.kind == "changed"
    assert e.previous == "Yes"
    t = ledger.tally("t1")
    assert t.counts == {"Yes": 0, "No": 1}
    assert t.standing == 1
    assert t.changes == 1


def test_history_is_append_only_and_complete() -> None:
    ledger, (a, *_) = _setup()
    ledger.cast(_v(a), "t1", "Yes")
    ledger.cast(_v(a), "t1", "No")
    ledger.withdraw(_v(a), "t1")
    kinds = [e.kind for e in ledger.history("t1", a)]
    assert kinds == ["cast", "changed", "withdrawn"]


def test_withdraw_removes_from_standing_but_not_from_ever() -> None:
    ledger, (a, b, *_) = _setup()
    ledger.cast(_v(a), "t1", "Yes")
    ledger.cast(_v(b), "t1", "Yes")
    ledger.withdraw(_v(a), "t1", reason="Undecided now")
    t = ledger.tally("t1")
    assert t.standing == 1
    assert t.ever_participated == 2
    assert t.withdrawn == 1
    assert ledger.current("t1", a) is None


def test_returning_after_withdrawal_counts_again() -> None:
    ledger, (a, *_) = _setup()
    ledger.cast(_v(a), "t1", "Yes")
    ledger.withdraw(_v(a), "t1")
    e = ledger.cast(_v(a), "t1", "No")
    assert e.kind == "cast"  # previous was None after withdrawal
    t = ledger.tally("t1")
    assert t.standing == 1
    assert t.withdrawn == 0


def test_same_choice_twice_is_rejected() -> None:
    ledger, (a, *_) = _setup()
    ledger.cast(_v(a), "t1", "Yes")
    with pytest.raises(ValueError, match="already stands"):
        ledger.cast(_v(a), "t1", "Yes")


def test_withdraw_without_standing_vote_is_rejected() -> None:
    ledger, (a, *_) = _setup()
    with pytest.raises(ValueError, match="No standing vote"):
        ledger.withdraw(_v(a), "t1")


def test_invalid_option_and_unverified_are_rejected() -> None:
    ledger, (a, *_) = _setup()
    with pytest.raises(ValueError, match="Invalid vote choice"):
        ledger.cast(_v(a), "t1", "Maybe")
    with pytest.raises(PermissionError):
        ledger.cast(_v(a, ok=False), "t1", "Yes")
    with pytest.raises(PermissionError):
        ledger.cast(_v("stranger"), "t1", "Yes")


def test_closed_topic_and_no_votes_topic_are_rejected() -> None:
    past = datetime.now(tz=UTC) - timedelta(hours=1)
    ledger, (a, *_) = _setup(closes_at=past)
    with pytest.raises(ValueError, match="closed"):
        ledger.cast(_v(a), "t1", "Yes")
    ledger2, (b, *_) = _setup(allow_votes=False)
    with pytest.raises(ValueError, match="does not accept votes"):
        ledger2.cast(_v(b), "t1", "Yes")


def test_reason_is_trimmed_and_optional() -> None:
    ledger, (a, *_) = _setup()
    e1 = ledger.cast(_v(a), "t1", "Yes", reason="   ")
    assert e1.reason is None
    e2 = ledger.cast(_v(a), "t1", "No", reason="  new data  ")
    assert e2.reason == "new data"


# --------------------------------------------------------------------------- #
# Tallies: deterministic, denominator included, replayable in time            #
# --------------------------------------------------------------------------- #


def test_tally_reports_every_declared_option_in_order() -> None:
    ledger, (a, *_) = _setup(vote_options=["Yes", "No", "Undecided"])
    ledger.cast(_v(a), "t1", "No")
    t = ledger.tally("t1")
    assert list(t.counts) == ["Yes", "No", "Undecided"]
    assert t.counts["No"] == 1
    assert t.share("No") == 1.0
    assert t.share("Yes") == 0.0


def test_empty_tally_has_zero_share_not_error() -> None:
    ledger, _ = _setup()
    t = ledger.tally("t1")
    assert t.standing == 0
    assert t.share("Yes") == 0.0


def test_tally_at_a_past_moment_replays_the_ledger() -> None:
    ledger, (a, b, c) = _setup()
    e1 = ledger.cast(_v(a), "t1", "Yes")
    e2 = ledger.cast(_v(b), "t1", "Yes")
    ledger.cast(_v(a), "t1", "No")
    ledger.cast(_v(c), "t1", "No")
    then = ledger.tally("t1", at=e2.at)
    assert then.counts == {"Yes": 2, "No": 0}
    assert then.at == e2.at
    before_anything = ledger.tally("t1", at=e1.at - timedelta(seconds=1))
    assert before_anything.standing == 0
    now = ledger.tally("t1")
    assert now.counts == {"Yes": 1, "No": 2}


def test_timeline_is_the_living_curve() -> None:
    ledger, (a, b, *_) = _setup()
    ledger.cast(_v(a), "t1", "Yes")
    ledger.cast(_v(b), "t1", "Yes")
    ledger.cast(_v(a), "t1", "No")
    curve = [(t.counts["Yes"], t.counts["No"]) for t in ledger.timeline("t1")]
    assert curve == [(1, 0), (2, 0), (1, 1)]


def test_participant_count_is_distinct_standing_voters() -> None:
    ledger, (a, b, *_) = _setup()
    ledger.cast(_v(a), "t1", "Yes")
    ledger.cast(_v(a), "t1", "No")
    ledger.cast(_v(b), "t1", "No")
    assert ledger.participant_count("t1") == 2


def test_tallies_are_per_topic() -> None:
    ledger, (a, *_) = _setup()
    ledger._topic_store.create(
        Topic(id="t2", title="Other", vote_options=["Yes", "No"])
    )
    ledger.cast(_v(a), "t1", "Yes")
    ledger.cast(_v(a), "t2", "No")
    assert ledger.tally("t1").counts == {"Yes": 1, "No": 0}
    assert ledger.tally("t2").counts == {"Yes": 0, "No": 1}


# --------------------------------------------------------------------------- #
# Migrations: what changed people's minds                                     #
# --------------------------------------------------------------------------- #


def test_migrations_group_moves_and_collect_reasons() -> None:
    ledger, (a, b, c) = _setup()
    for vid in (a, b, c):
        ledger.cast(_v(vid), "t1", "Yes")
    ledger.cast(_v(a), "t1", "No", reason="cost report")
    ledger.cast(_v(b), "t1", "No", reason="cost report")
    ledger.withdraw(_v(c), "t1", reason="need more data")
    moves = ledger.migrations("t1")
    assert [(m.from_choice, m.to_choice, m.count) for m in moves] == [
        ("Yes", "No", 2),
        ("Yes", None, 1),
    ]
    assert moves[0].reasons == ["cost report", "cost report"]
    assert moves[1].reasons == ["need more data"]


def test_first_casts_are_not_migrations() -> None:
    ledger, (a, *_) = _setup()
    ledger.cast(_v(a), "t1", "Yes", reason="I like transit")
    assert ledger.migrations("t1") == []
