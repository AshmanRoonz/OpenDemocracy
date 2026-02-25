"""NLP pipeline: text cleaning, tokenization, and embedding generation."""

from __future__ import annotations

import logging
import re

from opendemocracy.models import Opinion

logger = logging.getLogger(__name__)

# Lightweight text cleaning — runs before any model sees the text
_WHITESPACE_RE = re.compile(r"\s+")
_PLACEHOLDER_RE = re.compile(r"\[(EMAIL|URL|PHONE|USER|SELF-ID)\]")


def clean_text(text: str) -> str:
    """Normalize whitespace, strip placeholders from anonymizer, lowercase."""
    text = _PLACEHOLDER_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip().lower()


class EmbeddingPipeline:
    """Generate sentence embeddings for opinion texts.

    Uses ``sentence-transformers`` with a small, fast model suitable for
    clustering opinion text. The model is loaded lazily on first use.
    """

    DEFAULT_MODEL = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model = None

    def _load_model(self):  # type: ignore[no-untyped-def]
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "Install sentence-transformers: pip install sentence-transformers"
            ) from exc
        self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_opinions(self, opinions: list[Opinion]) -> list[Opinion]:
        """Add embedding vectors to each opinion in-place and return them."""
        model = self._model or self._load_model()

        texts = [clean_text(op.text) for op in opinions]
        embeddings = model.encode(texts, show_progress_bar=False)

        for opinion, vec in zip(opinions, embeddings):
            opinion.embedding = vec.tolist()

        logger.info("Embedded %d opinions with model '%s'", len(opinions), self.model_name)
        return opinions
