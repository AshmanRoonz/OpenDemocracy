"""Tests for *what needs attention?* — flow handing over to choice."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import (
    BiometricFactor,
    EnrollmentRecord,
    Topic,
    VerificationResult,
)
from opendemocracy.participation.attention import (
    AGENDA_PROMPT,
    WEIGHTS,
    AttentionReason,
    what_needs_attention,
)
from opendemocracy.participation.preferences import PreferenceProfile
from opendemocracy.participation.relevance import Interests
from opendemocracy.participation.topics import TopicStore
from opendemocracy.participation.votes import StandingVoteLedger

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _ledger(n: int = 6) -> tuple[StandingVoteLedger, TopicStore, list[str]]:
    reg = IdentityRegistry()
    ids = []
    for i in range(n):
        vid = f"v{i}"
        reg.register(
            EnrollmentRecord(
                anonymous_id=vid,
                public_key=f"pk{i}",
                factors_enrolled=[BiometricFactor.FINGERPRINT, BiometricFactor.FACE],
            )
        )
        ids.append(vid)
    topics = TopicStore()
    return StandingVoteLedger(topics, reg), topics, ids


def _v(vid: str) -> VerificationResult:
    return VerificationResult(verified=True, anonymous_id=vid)


def _topic(**kw: object) -> Topic:
    d: dict[str, object] = {
        "id": "t1",
        "title": "T",
        "created_at": NOW,
        "vote_options": ["Yes", "No"],
    }
    d.update(kw)
    return Topic(**d)  # type: ignore[arg-type]


def _reasons(items, topic_id="t1"):  # type: ignore[no-untyped-def]
    for it in items:
        if it.topic.id == topic_id:
            return it.reasons
    return []


def test_agenda_prompt_is_the_reverse_question() -> None:
    assert "nobody has asked" in AGENDA_PROMPT


def test_silence_is_a_valid_answer() -> None:
    assert what_needs_attention([_topic()], Interests(), now=NOW) == []


def test_not_yet_heard_when_relevant_and_silent() -> None:
    items = what_needs_attention(
        [_topic(tags=["housing"])], Interests(tags=["housing"]), now=NOW
    )
    assert _reasons(items) == [AttentionReason.NOT_YET_HEARD]
    assert items[0].score == WEIGHTS[AttentionReason.NOT_YET_HEARD]


def test_closed_topics_never_need_attention() -> None:
    t = _topic(tags=["housing"], closes_at=NOW - timedelta(hours=1))
    assert what_needs_attention([t], Interests(tags=["housing"]), now=NOW) == []


def test_unknown_values_when_profile_cannot_project() -> None:
    t = _topic(value_alignments={"defense": 1.0})
    items = what_needs_attention([t], Interests(), profile=PreferenceProfile(), now=NOW)
    assert _reasons(items) == [AttentionReason.UNKNOWN_VALUES]


def test_value_conflict_outranks_everything() -> None:
    p = PreferenceProfile()
    for _ in range(5):
        p.record_signal("public-services", 1.0, "survey")
        p.record_signal("taxes-low", 1.0, "survey")
    conflict = _topic(
        id="c", value_alignments={"public-services": 1.0, "taxes-low": -1.0}
    )
    aligned = _topic(id="a", value_alignments={"public-services": 1.0}, tags=["x"])
    items = what_needs_attention(
        [aligned, conflict], Interests(tags=["x"]), profile=p, now=NOW
    )
    assert [i.topic.id for i in items] == ["c", "a"]
    assert _reasons(items, "c") == [AttentionReason.VALUE_CONFLICT]
    assert "conflict" in items[0].explanations[0]
    assert _reasons(items, "a") == [AttentionReason.NOT_YET_HEARD]


def test_no_conflict_when_values_agree() -> None:
    p = PreferenceProfile()
    for _ in range(5):
        p.record_signal("public-services", 1.0, "survey")
    t = _topic(value_alignments={"public-services": 1.0})
    assert what_needs_attention([t], Interests(), profile=p, now=NOW) == []


def test_peers_moving_after_a_wave_from_my_stance() -> None:
    ledger, topics, ids = _ledger()
    topics.create(_topic())
    ledger.cast(_v(ids[5]), "t1", "No")
    for vid in ids[1:5]:
        ledger.cast(_v(vid), "t1", "Yes")
    me = ids[0]
    ledger.cast(_v(me), "t1", "Yes")  # I choose last: 5/6 Yes at that moment
    # Nobody has moved yet: my vote stands, nothing to see.
    assert (
        what_needs_attention(
            [topics.get("t1")], Interests(), ledger=ledger, voter_id=me, now=NOW
        )
        == []
    )  # type: ignore[list-item]
    for vid in ids[1:4]:
        ledger.cast(_v(vid), "t1", "No", reason="cost report")
    items = what_needs_attention(
        [topics.get("t1")], Interests(), ledger=ledger, voter_id=me, now=NOW
    )  # type: ignore[list-item]
    reasons = _reasons(items)
    assert AttentionReason.PEERS_MOVING in reasons
    assert AttentionReason.STALE_VOTE in reasons  # Yes went from 83% to 33%
    assert any("3 people" in e for e in items[0].explanations)


def test_stale_vote_without_a_wave() -> None:
    ledger, topics, ids = _ledger()
    topics.create(_topic())
    me = ids[0]
    ledger.cast(_v(me), "t1", "Yes")  # 100% Yes at the moment I chose
    for vid in ids[1:4]:
        ledger.cast(_v(vid), "t1", "No")  # newcomers, not movers
    items = what_needs_attention(
        [topics.get("t1")], Interests(), ledger=ledger, voter_id=me, now=NOW
    )  # type: ignore[list-item]
    assert _reasons(items) == [AttentionReason.STALE_VOTE]


def test_not_yet_heard_uses_my_standing_vote_when_ledger_given() -> None:
    ledger, topics, ids = _ledger()
    topics.create(_topic(tags=["housing"]))
    me = ids[0]
    interests = Interests(tags=["housing"])
    assert _reasons(
        what_needs_attention(
            [topics.get("t1")], interests, ledger=ledger, voter_id=me, now=NOW
        )
    ) == [  # type: ignore[list-item]
        AttentionReason.NOT_YET_HEARD
    ]
    ledger.cast(_v(me), "t1", "Yes")
    assert (
        what_needs_attention(
            [topics.get("t1")], interests, ledger=ledger, voter_id=me, now=NOW
        )
        == []
    )  # type: ignore[list-item]


def test_closing_soon_and_quorum_near() -> None:
    ledger, topics, ids = _ledger()
    topics.create(_topic(closes_at=NOW + timedelta(hours=10), quorum=5))
    for vid in ids[:4]:
        ledger.cast(_v(vid), "t1", "Yes")
    items = what_needs_attention(
        [topics.get("t1")], Interests(), ledger=ledger, now=NOW
    )  # type: ignore[list-item]
    assert _reasons(items) == [
        AttentionReason.CLOSING_SOON,
        AttentionReason.QUORUM_NEAR,
    ]
    ledger.cast(_v(ids[4]), "t1", "Yes")  # quorum reached: no longer "near"
    items = what_needs_attention(
        [topics.get("t1")], Interests(), ledger=ledger, now=NOW
    )  # type: ignore[list-item]
    assert _reasons(items) == [AttentionReason.CLOSING_SOON]


def test_ties_break_by_relevance_then_newest() -> None:
    a = _topic(id="a", tags=["housing"], created_at=NOW - timedelta(days=1))
    b = _topic(id="b", tags=["housing", "tax"], created_at=NOW)
    c = _topic(id="c", tags=["housing"], created_at=NOW)
    items = what_needs_attention([a, b, c], Interests(tags=["housing"]), now=NOW)
    # a and c: full tag match (1.0 of topic tags); b: half. Newest first among a/c.
    assert [i.topic.id for i in items] == ["c", "a", "b"]
