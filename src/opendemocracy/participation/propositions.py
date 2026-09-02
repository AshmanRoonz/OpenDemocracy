"""Proposition merging with visible framing variants.

"Anyone can vote for anything" has a mechanical problem: the same question
gets asked in many wordings, and the signal fragments across them. Vote's
answer is to **merge duplicates into one proposition while keeping every
wording visible**, because "ban X" and "allow X" polling differently is not
noise — it is framing-effect data, and hiding it would be a distortion of
exactly the kind Vote exists to remove.

Rules enforced here:

* **AI suggests, humans merge.** Similarity is a transparent lexical measure
  (shared terms, shared tags) that anyone can recompute. A suggestion becomes
  a merge only through an explicit ``merge`` call, recorded with its reason.
* **Merging never deletes a wording.** Each topic keeps its own tally. The
  proposition adds a combined view; it does not replace the variants.
* **The combined tally counts people, not votes.** Someone who voted on two
  wordings counts once, by their most recent stance across all of them.
* **Divergence is reported, never smoothed.** How far the wordings disagree
  is a first-class number shown next to the combined result.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from opendemocracy.models import Topic
from opendemocracy.participation.relevance import _aware
from opendemocracy.participation.topics import TopicStore
from opendemocracy.participation.votes import StandingVoteLedger, Tally

# Lexical similarity at or above this is suggested as a possible duplicate.
MERGE_SUGGEST_THRESHOLD = 0.5
# Shared terms carry most of the weight; shared tags confirm.
WEIGHT_TERMS = 0.8
WEIGHT_TAGS = 0.2
# Framings must each have this many standing voters before their disagreement
# is reported — a wording with two votes can't "diverge".
DIVERGENCE_MIN_STANDING = 5
# Wordings diverge when some option's share differs by at least this much.
FRAMING_DIVERGENCE_MIN = 0.10

_STOP = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "is",
        "are",
        "be",
        "should",
        "we",
        "our",
        "this",
        "that",
        "it",
        "its",
        "with",
        "by",
        "at",
        "from",
        "as",
        "do",
        "does",
        "can",
        "will",
        "would",
    ]
)


def _stem(word: str) -> str:
    """Minimal, readable normalization: plurals only ("cars" -> "car")."""
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _terms(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {_stem(w) for w in words if w not in _STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


@dataclass
class MergeSuggestion:
    """Two topics that may be the same question — with the evidence shown."""

    topic_a: str
    topic_b: str
    score: float
    shared_terms: list[str]
    shared_tags: list[str]


def similarity(a: Topic, b: Topic) -> float:
    """Transparent 0-1 similarity: shared terms in title/description, shared tags."""
    ta, tb = (
        _terms(a.title + " " + a.description),
        _terms(b.title + " " + b.description),
    )
    tags_a = {t.strip().lower() for t in a.tags if t.strip()}
    tags_b = {t.strip().lower() for t in b.tags if t.strip()}
    term_sim = _jaccard(ta, tb)
    if not tags_a or not tags_b:
        return term_sim  # nothing to confirm with; terms carry it alone
    return WEIGHT_TERMS * term_sim + WEIGHT_TAGS * _jaccard(tags_a, tags_b)


def suggest_merges(
    topics: list[Topic], threshold: float = MERGE_SUGGEST_THRESHOLD
) -> list[MergeSuggestion]:
    """Pairs that look like the same question, strongest first. Never merges."""
    out: list[MergeSuggestion] = []
    for i, a in enumerate(topics):
        for b in topics[i + 1 :]:
            if a.proposition_id is not None and a.proposition_id == b.proposition_id:
                continue  # already together
            score = similarity(a, b)
            if score >= threshold:
                shared = _terms(a.title + " " + a.description) & _terms(
                    b.title + " " + b.description
                )
                tags = {t.lower() for t in a.tags} & {t.lower() for t in b.tags}
                out.append(
                    MergeSuggestion(
                        a.id, b.id, round(score, 4), sorted(shared), sorted(tags)
                    )
                )
    return sorted(out, key=lambda s: -s.score)


@dataclass
class MergeEvent:
    """Audit record: who declared which wordings to be one proposition, and why."""

    proposition_id: str
    topic_ids: list[str]
    reason: str | None
    by: str | None  # anonymous id of the person who merged, if known
    kind: str = "merge"  # "merge" | "split"
    at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))


@dataclass
class FramingVariant:
    """One wording of a proposition and where its voters stand."""

    topic_id: str
    title: str
    tally: Tally


@dataclass
class PropositionView:
    """A proposition: its wordings, their tallies, combined people-count, divergence."""

    proposition_id: str
    variants: list[FramingVariant]
    combined: Tally
    divergence: float  # largest gap between wordings on any option's share
    divergence_option: str | None  # the option where wordings disagree most

    @property
    def framing_matters(self) -> bool:
        return self.divergence >= FRAMING_DIVERGENCE_MIN


class PropositionRegistry:
    """Declare and inspect propositions over topics in a :class:`TopicStore`."""

    def __init__(self, topic_store: TopicStore, ledger: StandingVoteLedger) -> None:
        self._topics = topic_store
        self._ledger = ledger
        self.history: list[MergeEvent] = []

    # -- declaring --------------------------------------------------------- #

    def merge(
        self,
        topic_ids: list[str],
        reason: str | None = None,
        by: str | None = None,
    ) -> str:
        """Declare these topics to be wordings of one proposition.

        If any of them already belongs to a proposition, the others join it;
        two existing propositions are unified under the first one found.
        Requires at least two distinct, existing topics with the same set of
        vote options — different options are different questions.
        """
        ids = list(dict.fromkeys(topic_ids))
        if len(ids) < 2:
            raise ValueError("A proposition needs at least two wordings")
        topics = []
        for tid in ids:
            t = self._topics.get(tid)
            if t is None:
                raise ValueError(f"Topic {tid!r} does not exist")
            topics.append(t)
        options = {tuple(sorted(o.lower() for o in t.vote_options)) for t in topics}
        if len(options) > 1:
            raise ValueError("Wordings must offer the same vote options to be merged")

        existing = [t.proposition_id for t in topics if t.proposition_id]
        pid = existing[0] if existing else uuid.uuid4().hex[:12]
        # Pull in every member of any proposition being unified.
        members = set(ids)
        for old in set(existing):
            members |= {t.id for t in self._members(old)}
        for tid in members:
            t = self._topics.get(tid)
            if t is not None:
                t.proposition_id = pid
        self.history.append(MergeEvent(pid, sorted(members), reason, by))
        return pid

    def split(
        self, topic_id: str, reason: str | None = None, by: str | None = None
    ) -> None:
        """Take one wording back out of its proposition. Its votes are untouched."""
        t = self._topics.get(topic_id)
        if t is None or t.proposition_id is None:
            raise ValueError(f"Topic {topic_id!r} is not part of a proposition")
        pid = t.proposition_id
        t.proposition_id = None
        self.history.append(MergeEvent(pid, [topic_id], reason, by, kind="split"))

    # -- inspecting -------------------------------------------------------- #

    def _members(self, proposition_id: str) -> list[Topic]:
        return [
            t
            for t in self._topics._topics.values()
            if t.proposition_id == proposition_id
        ]

    def variants(self, topic_id: str) -> list[Topic]:
        """All wordings sharing this topic's proposition (including itself)."""
        t = self._topics.get(topic_id)
        if t is None or t.proposition_id is None:
            return [t] if t else []
        return sorted(self._members(t.proposition_id), key=lambda x: x.id)

    def view(self, topic_id: str, at: datetime | None = None) -> PropositionView | None:
        """Combined view for the proposition this topic belongs to, or ``None``."""
        t = self._topics.get(topic_id)
        if t is None or t.proposition_id is None:
            return None
        members = self.variants(topic_id)
        variants = [
            FramingVariant(m.id, m.title, self._ledger.tally(m.id, at)) for m in members
        ]
        combined = self._combined(t.proposition_id, members, at)
        divergence, option = self._divergence(variants, combined)
        return PropositionView(t.proposition_id, variants, combined, divergence, option)

    def _combined(
        self, proposition_id: str, members: list[Topic], at: datetime | None
    ) -> Tally:
        """One person, one stance across all wordings: their latest event wins."""
        cutoff = _aware(at) if at else None
        events = [
            e
            for m in members
            for e in self._ledger.history(m.id)
            if cutoff is None or _aware(e.at) <= cutoff
        ]
        events.sort(key=lambda e: _aware(e.at))
        standing: dict[str, str | None] = {}
        changes = 0
        for e in events:
            if e.kind == "changed":
                changes += 1
            standing[e.anonymous_voter_id] = e.choice
        options = list(members[0].vote_options) if members else []
        extra = sorted({c for c in standing.values() if c and c not in options})
        counts = {o: 0 for o in options + extra}
        for c in standing.values():
            if c is not None:
                counts[c] += 1
        last = events[-1].at if events else datetime.now(tz=UTC)
        return Tally(
            topic_id=proposition_id,
            at=cutoff or last,
            counts=counts,
            standing=sum(counts.values()),
            ever_participated=len(standing),
            withdrawn=sum(1 for c in standing.values() if c is None),
            changes=changes,
        )

    @staticmethod
    def _divergence(
        variants: list[FramingVariant], combined: Tally
    ) -> tuple[float, str | None]:
        """Largest gap between wordings on any option's share, or 0 if too thin."""
        big = [v for v in variants if v.tally.standing >= DIVERGENCE_MIN_STANDING]
        if len(big) < 2:
            return 0.0, None
        worst, where = 0.0, None
        for option in combined.counts:
            shares = [v.tally.share(option) for v in big]
            gap = max(shares) - min(shares)
            if gap > worst:
                worst, where = gap, option
        return round(worst, 4), where
