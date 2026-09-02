"""Tests for proposition merging with visible framing variants."""

from __future__ import annotations

import pytest

from opendemocracy.identity.registry import IdentityRegistry
from opendemocracy.models import (
    BiometricFactor,
    EnrollmentRecord,
    Topic,
    VerificationResult,
)
from opendemocracy.participation.attention import AttentionReason, what_needs_attention
from opendemocracy.participation.propositions import (
    FRAMING_DIVERGENCE_MIN,
    MERGE_SUGGEST_THRESHOLD,
    PropositionRegistry,
    similarity,
    suggest_merges,
)
from opendemocracy.participation.relevance import Interests
from opendemocracy.participation.topics import TopicStore
from opendemocracy.participation.votes import StandingVoteLedger


def _world(
    n: int = 12,
) -> tuple[TopicStore, StandingVoteLedger, PropositionRegistry, list[str]]:
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
    ledger = StandingVoteLedger(topics, reg)
    return topics, ledger, PropositionRegistry(topics, ledger), ids


def _v(vid: str) -> VerificationResult:
    return VerificationResult(verified=True, anonymous_id=vid)


BAN = Topic(
    id="ban",
    title="Ban cars from the city centre",
    tags=["transport"],
    vote_options=["Yes", "No"],
)
FREE = Topic(
    id="free",
    title="Make the city centre car-free",
    tags=["transport"],
    vote_options=["Yes", "No"],
)
DOGS = Topic(
    id="dogs", title="Allow dogs in parks", tags=["parks"], vote_options=["Yes", "No"]
)


# --------------------------------------------------------------------------- #
# Suggesting                                                                  #
# --------------------------------------------------------------------------- #


def test_similarity_is_transparent_and_symmetric() -> None:
    assert similarity(BAN, FREE) == similarity(FREE, BAN)
    assert similarity(BAN, FREE) > similarity(BAN, DOGS)
    assert similarity(BAN, FREE) >= MERGE_SUGGEST_THRESHOLD
    assert similarity(BAN, DOGS) < MERGE_SUGGEST_THRESHOLD


def test_suggest_merges_shows_its_evidence_and_never_merges() -> None:
    s = suggest_merges([BAN, FREE, DOGS])
    assert [(x.topic_a, x.topic_b) for x in s] == [("ban", "free")]
    assert "centre" in s[0].shared_terms and "city" in s[0].shared_terms
    assert s[0].shared_tags == ["transport"]
    assert BAN.proposition_id is None and FREE.proposition_id is None


def test_already_merged_pairs_are_not_suggested_again() -> None:
    topics, _, registry, _ = _world()
    a = Topic(id="a", title="Ban cars from the city centre", vote_options=["Yes", "No"])
    b = Topic(
        id="b", title="Ban all cars from the city centre", vote_options=["Yes", "No"]
    )
    topics.create(a)
    topics.create(b)
    assert suggest_merges([a, b])
    registry.merge(["a", "b"])
    assert suggest_merges([a, b]) == []


# --------------------------------------------------------------------------- #
# Merging and splitting                                                       #
# --------------------------------------------------------------------------- #


def test_merge_links_wordings_and_records_why() -> None:
    topics, _, registry, _ = _world()
    for t in (BAN, FREE):
        topics.create(Topic(**{**t.__dict__}))
    pid = registry.merge(["ban", "free"], reason="same question", by="v0")
    assert topics.get("ban").proposition_id == pid  # type: ignore[union-attr]
    assert [t.id for t in registry.variants("ban")] == ["ban", "free"]
    assert registry.history[-1].reason == "same question"
    assert registry.history[-1].by == "v0"
    assert registry.history[-1].topic_ids == ["ban", "free"]


def test_merge_requires_two_existing_topics_with_same_options() -> None:
    topics, _, registry, _ = _world()
    topics.create(Topic(id="a", title="A", vote_options=["Yes", "No"]))
    topics.create(Topic(id="b", title="B", vote_options=["Agree", "Disagree"]))
    with pytest.raises(ValueError, match="at least two"):
        registry.merge(["a", "a"])
    with pytest.raises(ValueError, match="does not exist"):
        registry.merge(["a", "ghost"])
    with pytest.raises(ValueError, match="same vote options"):
        registry.merge(["a", "b"])


def test_merging_into_an_existing_proposition_unifies() -> None:
    topics, _, registry, _ = _world()
    for i in "abc":
        topics.create(Topic(id=i, title=i, vote_options=["Yes", "No"]))
    pid = registry.merge(["a", "b"])
    assert registry.merge(["b", "c"]) == pid
    assert [t.id for t in registry.variants("c")] == ["a", "b", "c"]


def test_split_takes_one_wording_out_and_keeps_its_votes() -> None:
    topics, ledger, registry, ids = _world()
    for i in "ab":
        topics.create(Topic(id=i, title=i, vote_options=["Yes", "No"]))
    registry.merge(["a", "b"])
    ledger.cast(_v(ids[0]), "b", "Yes")
    registry.split("b", reason="different question after all")
    assert topics.get("b").proposition_id is None  # type: ignore[union-attr]
    assert registry.variants("b") == [topics.get("b")]
    assert ledger.tally("b").standing == 1
    assert registry.history[-1].kind == "split"
    with pytest.raises(ValueError):
        registry.split("b")


# --------------------------------------------------------------------------- #
# Combined view                                                               #
# --------------------------------------------------------------------------- #


def test_view_is_none_when_not_merged() -> None:
    topics, _, registry, _ = _world()
    topics.create(Topic(id="a", title="A", vote_options=["Yes", "No"]))
    assert registry.view("a") is None


def test_combined_tally_counts_people_once_by_latest_stance() -> None:
    topics, ledger, registry, ids = _world()
    for i in "ab":
        topics.create(Topic(id=i, title=i, vote_options=["Yes", "No"]))
    registry.merge(["a", "b"])
    ledger.cast(_v(ids[0]), "a", "Yes")
    ledger.cast(_v(ids[0]), "b", "No")  # same person, other wording, later
    ledger.cast(_v(ids[1]), "a", "Yes")
    view = registry.view("a")
    assert view is not None
    assert view.combined.counts == {"Yes": 1, "No": 1}
    assert view.combined.standing == 2
    assert view.combined.ever_participated == 2
    # Each wording still shows its own tally, untouched.
    assert {v.topic_id: v.tally.counts for v in view.variants} == {
        "a": {"Yes": 2, "No": 0},
        "b": {"Yes": 0, "No": 1},
    }


def test_divergence_needs_enough_voters_on_each_wording() -> None:
    topics, ledger, registry, ids = _world()
    for i in "ab":
        topics.create(Topic(id=i, title=i, vote_options=["Yes", "No"]))
    registry.merge(["a", "b"])
    ledger.cast(_v(ids[0]), "a", "Yes")
    ledger.cast(_v(ids[1]), "b", "No")
    view = registry.view("a")
    assert view is not None
    assert view.divergence == 0.0 and view.divergence_option is None
    assert not view.framing_matters


def test_divergence_is_the_largest_gap_between_wordings() -> None:
    topics, ledger, registry, ids = _world()
    for i in "ab":
        topics.create(Topic(id=i, title=i, vote_options=["Yes", "No"]))
    registry.merge(["a", "b"])
    for vid in ids[:5]:
        ledger.cast(_v(vid), "a", "Yes")  # wording a: 100% Yes
    for vid in ids[5:8]:
        ledger.cast(_v(vid), "b", "Yes")
    for vid in ids[8:10]:
        ledger.cast(_v(vid), "b", "No")  # wording b: 60% Yes
    view = registry.view("a")
    assert view is not None
    assert view.divergence == pytest.approx(0.4)
    assert view.divergence_option == "Yes"
    assert view.framing_matters
    assert view.divergence >= FRAMING_DIVERGENCE_MIN


# --------------------------------------------------------------------------- #
# Attention: framing matters                                                  #
# --------------------------------------------------------------------------- #


def _diverging_world():  # type: ignore[no-untyped-def]
    topics, ledger, registry, ids = _world()
    topics.create(
        Topic(id="a", title="Ban cars", tags=["transport"], vote_options=["Yes", "No"])
    )
    topics.create(
        Topic(
            id="b",
            title="Car-free centre",
            tags=["transport"],
            vote_options=["Yes", "No"],
        )
    )
    registry.merge(["a", "b"])
    for vid in ids[:5]:
        ledger.cast(_v(vid), "a", "Yes")
    for vid in ids[5:8]:
        ledger.cast(_v(vid), "b", "Yes")
    for vid in ids[8:10]:
        ledger.cast(_v(vid), "b", "No")
    return topics, ledger, registry, ids


def test_framing_matters_surfaces_for_a_voter_on_any_wording() -> None:
    topics, ledger, registry, ids = _diverging_world()
    items = what_needs_attention(
        topics.list_open(),
        Interests(),
        ledger=ledger,
        voter_id=ids[0],
        registry=registry,
    )
    by_id = {i.topic.id: i for i in items}
    assert AttentionReason.FRAMING_MATTERS in by_id["a"].reasons
    assert AttentionReason.FRAMING_MATTERS in by_id["b"].reasons
    assert any("40%" in e for e in by_id["a"].explanations)


def test_framing_matters_surfaces_for_relevant_interests_without_a_vote() -> None:
    topics, ledger, registry, ids = _diverging_world()
    items = what_needs_attention(
        topics.list_open(),
        Interests(tags=["transport"]),
        ledger=ledger,
        voter_id=ids[11],
        registry=registry,
    )
    reasons = {i.topic.id: i.reasons for i in items}
    assert AttentionReason.FRAMING_MATTERS in reasons["a"]
    assert AttentionReason.NOT_YET_HEARD in reasons["a"]


def test_framing_is_silent_when_neither_yours_nor_relevant() -> None:
    topics, ledger, registry, ids = _diverging_world()
    items = what_needs_attention(
        topics.list_open(),
        Interests(tags=["parks"]),
        ledger=ledger,
        voter_id=ids[11],
        registry=registry,
    )
    assert items == []


def test_framing_is_silent_without_a_registry() -> None:
    topics, ledger, _, ids = _diverging_world()
    items = what_needs_attention(
        topics.list_open(), Interests(), ledger=ledger, voter_id=ids[0]
    )
    assert all(AttentionReason.FRAMING_MATTERS not in i.reasons for i in items)
