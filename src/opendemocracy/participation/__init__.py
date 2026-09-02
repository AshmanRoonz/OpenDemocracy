"""Participation layer: verified submission of opinions, ideas, and votes.

Every submission requires a valid biometric verification.  The system
enforces **one submission per person per topic** — once you've submitted
your opinion, idea, or vote on a topic, that's your one entry.  This is
enforced by the anonymous voter ID from the identity layer.

The :mod:`~opendemocracy.participation.relevance` module adds the *frequent
democracy* feed: ranking open issues by how relevant, urgent, and active they
are for a given citizen, so voices are invited in when an issue concerns them.

The :mod:`~opendemocracy.participation.votes` module holds *standing* votes: one
revocable, changeable vote per person per topic, kept as an append-only ledger
so tallies are replayable at any moment and changed minds are visible data.

The :mod:`~opendemocracy.participation.attention` module answers *what needs
attention?* — the point where automatic flow (projected preferences, standing
votes) hands over to choice, with every claim on attention naming its reason.

The :mod:`~opendemocracy.participation.propositions` module merges duplicate
questions into one proposition while keeping every wording visible, so the
signal doesn't fragment and framing effects are shown rather than hidden.

The :mod:`~opendemocracy.participation.findings` module freezes an issue into
a *Finding*: a hashed, reproducible, exportable snapshot — the citable record
at the top of the legitimacy ladder.
"""

from opendemocracy.participation.attention import (
    AGENDA_PROMPT,
    AttentionItem,
    AttentionReason,
    what_needs_attention,
)
from opendemocracy.participation.findings import (
    Finding,
    FindingStore,
    LadderRung,
    ladder_rung,
)
from opendemocracy.participation.propositions import (
    MergeSuggestion,
    PropositionRegistry,
    PropositionView,
    similarity,
    suggest_merges,
)
from opendemocracy.participation.relevance import (
    Interests,
    activity_score,
    composite_score,
    matches_interests,
    rank_topics,
    region_matches,
    relevance_score,
    urgency_score,
)
from opendemocracy.participation.status import (
    TopicState,
    TopicStatus,
    compute_status,
    is_closed,
    quorum_fraction,
)
from opendemocracy.participation.submissions import SubmissionStore
from opendemocracy.participation.topics import TopicStore
from opendemocracy.participation.votes import (
    Migration,
    StandingVoteLedger,
    Tally,
    VoteEvent,
)

__all__ = [
    "AGENDA_PROMPT",
    "AttentionItem",
    "AttentionReason",
    "Finding",
    "FindingStore",
    "Interests",
    "LadderRung",
    "MergeSuggestion",
    "Migration",
    "PropositionRegistry",
    "PropositionView",
    "StandingVoteLedger",
    "SubmissionStore",
    "Tally",
    "TopicState",
    "TopicStatus",
    "TopicStore",
    "activity_score",
    "composite_score",
    "compute_status",
    "is_closed",
    "ladder_rung",
    "matches_interests",
    "quorum_fraction",
    "rank_topics",
    "region_matches",
    "relevance_score",
    "similarity",
    "suggest_merges",
    "urgency_score",
    "VoteEvent",
    "what_needs_attention",
]
