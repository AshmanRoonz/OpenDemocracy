"""Multi-dimensional sentiment analysis.

Goes beyond simple positive/negative polarity to capture dimensions relevant
to policy discussion: support/opposition, urgency, certainty, and emotional
intensity.
"""

from __future__ import annotations

import logging
import math

from opendemocracy.models import Opinion
from opendemocracy.processing.nlp import clean_text

logger = logging.getLogger(__name__)

# Keywords associated with each sentiment dimension (simple lexicon approach).
# A production system would use a fine-tuned classifier, but this provides a
# transparent, auditable baseline that can run without a GPU.

_SUPPORT_WORDS = frozenset({
    "support", "favor", "agree", "benefit", "good", "positive", "help",
    "advantage", "pro", "should", "need", "must", "important", "essential",
    "necessary", "great", "works", "effective", "promising",
})

_OPPOSE_WORDS = frozenset({
    "oppose", "against", "disagree", "harmful", "bad", "negative", "hurt",
    "disadvantage", "con", "shouldn't", "terrible", "fail", "waste",
    "dangerous", "risk", "problem", "worse", "costly", "ineffective",
})

_URGENCY_WORDS = frozenset({
    "now", "immediately", "urgent", "crisis", "emergency", "asap",
    "critical", "desperate", "overdue", "finally", "enough",
})

_CERTAINTY_WORDS = frozenset({
    "definitely", "certainly", "clearly", "obviously", "proven",
    "evidence", "fact", "data", "research", "study", "shows",
})

_UNCERTAINTY_WORDS = frozenset({
    "maybe", "perhaps", "might", "possibly", "unclear", "uncertain",
    "debatable", "depends", "unsure", "questionable",
})


def _word_ratio(words: list[str], lexicon: frozenset[str]) -> float:
    """Fraction of *words* that appear in *lexicon*."""
    if not words:
        return 0.0
    hits = sum(1 for w in words if w in lexicon)
    return hits / len(words)


def score_opinion(opinion: Opinion) -> Opinion:
    """Compute multi-dimensional sentiment scores for a single opinion.

    Scores are floats in [-1, 1] (for stance) or [0, 1] (for other dims).
    Results are stored in ``opinion.sentiment_scores`` in-place.
    """
    words = clean_text(opinion.text).split()

    support = _word_ratio(words, _SUPPORT_WORDS)
    oppose = _word_ratio(words, _OPPOSE_WORDS)
    stance = support - oppose  # [-1, 1]

    urgency = min(_word_ratio(words, _URGENCY_WORDS) * 5, 1.0)

    certainty_pos = _word_ratio(words, _CERTAINTY_WORDS)
    certainty_neg = _word_ratio(words, _UNCERTAINTY_WORDS)
    certainty = math.tanh((certainty_pos - certainty_neg) * 5)  # [-1, 1]

    # Emotional intensity: rough proxy using exclamation marks, caps ratio, word count
    raw_text = opinion.text
    excl = raw_text.count("!")
    caps_ratio = sum(1 for c in raw_text if c.isupper()) / max(len(raw_text), 1)
    intensity = min((excl * 0.15 + caps_ratio) * 2, 1.0)

    opinion.sentiment_scores = {
        "stance": round(stance, 4),
        "urgency": round(urgency, 4),
        "certainty": round(certainty, 4),
        "intensity": round(intensity, 4),
    }
    return opinion


def score_opinions(opinions: list[Opinion]) -> list[Opinion]:
    """Score a batch of opinions."""
    for op in opinions:
        score_opinion(op)
    logger.info("Scored sentiment for %d opinions", len(opinions))
    return opinions
