"""Opinion clustering using HDBSCAN or K-Means.

Groups opinions with similar embedding vectors into clusters,
then summarizes each cluster's characteristics.
"""

from __future__ import annotations

import logging
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans

from opendemocracy.models import ClusterResult, Opinion

logger = logging.getLogger(__name__)


def _try_hdbscan(embeddings: np.ndarray, min_cluster_size: int = 5) -> np.ndarray | None:
    """Attempt HDBSCAN clustering; return labels or None if unavailable."""
    try:
        from hdbscan import HDBSCAN  # type: ignore[import-untyped]

        clusterer = HDBSCAN(min_cluster_size=min_cluster_size)
        return clusterer.fit_predict(embeddings)
    except ImportError:
        return None


def cluster_opinions(
    opinions: list[Opinion],
    *,
    n_clusters: int = 5,
    min_cluster_size: int = 5,
    method: str = "auto",
) -> list[ClusterResult]:
    """Cluster opinions by their embeddings and return cluster summaries.

    Parameters
    ----------
    opinions:
        Opinions with populated ``embedding`` fields.
    n_clusters:
        Number of clusters for K-Means (ignored if HDBSCAN is used).
    min_cluster_size:
        Minimum cluster size for HDBSCAN.
    method:
        ``"auto"`` tries HDBSCAN first, falls back to K-Means.
        ``"hdbscan"`` or ``"kmeans"`` force a specific method.
    """
    embeddings = np.array([op.embedding for op in opinions])

    labels: np.ndarray | None = None

    if method in ("auto", "hdbscan"):
        labels = _try_hdbscan(embeddings, min_cluster_size)
        if labels is not None:
            logger.info("Using HDBSCAN clustering")

    if labels is None:
        actual_k = min(n_clusters, len(opinions))
        km = KMeans(n_clusters=actual_k, n_init=10, random_state=42)
        labels = km.fit_predict(embeddings)
        logger.info("Using K-Means clustering with k=%d", actual_k)

    # Assign cluster IDs back to opinions
    for opinion, label in zip(opinions, labels):
        opinion.cluster_id = int(label)

    # Build cluster summaries
    return _summarize_clusters(opinions)


def _summarize_clusters(opinions: list[Opinion]) -> list[ClusterResult]:
    """Build a ClusterResult for each cluster found."""
    clusters_map: dict[int, list[Opinion]] = {}
    for op in opinions:
        clusters_map.setdefault(op.cluster_id, []).append(op)

    results: list[ClusterResult] = []
    for cid, members in sorted(clusters_map.items()):
        # Pick representative texts (closest to cluster centroid by sentiment)
        sorted_by_length = sorted(members, key=lambda o: len(o.text), reverse=True)
        reps = [m.text[:200] for m in sorted_by_length[:3]]

        # Mean sentiment
        mean_sent: dict[str, float] = {}
        if members[0].sentiment_scores:
            keys = members[0].sentiment_scores.keys()
            for key in keys:
                vals = [m.sentiment_scores.get(key, 0.0) for m in members]
                mean_sent[key] = round(sum(vals) / len(vals), 4)

        # Demographic breakdown
        demo_breakdown: dict[str, dict[str, int]] = {}
        for dim in ("age_range", "region", "employment_status", "income_bracket"):
            counts: Counter[str] = Counter()
            for m in members:
                val = getattr(m.demographics, dim, None)
                if val:
                    counts[val] += 1
            if counts:
                demo_breakdown[dim] = dict(counts)

        # Stance distribution
        stance_dist: dict[str, float] = {}
        stances = [m.sentiment_scores.get("stance", 0.0) for m in members if m.sentiment_scores]
        if stances:
            n = len(stances)
            stance_dist = {
                "support": round(sum(1 for s in stances if s > 0.02) / n, 4),
                "neutral": round(sum(1 for s in stances if -0.02 <= s <= 0.02) / n, 4),
                "oppose": round(sum(1 for s in stances if s < -0.02) / n, 4),
            }

        results.append(
            ClusterResult(
                cluster_id=cid,
                label=f"Cluster {cid}",
                size=len(members),
                representative_texts=reps,
                mean_sentiment=mean_sent,
                demographic_breakdown=demo_breakdown,
                stance_distribution=stance_dist,
            )
        )

    logger.info("Summarized %d clusters", len(results))
    return results
