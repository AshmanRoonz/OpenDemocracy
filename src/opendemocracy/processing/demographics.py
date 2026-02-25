"""Demographic contextualization — analyze how views vary across groups."""

from __future__ import annotations

import logging
from collections import defaultdict

from opendemocracy.models import ClusterResult, Opinion

logger = logging.getLogger(__name__)


def breakdown_by_demographic(
    opinions: list[Opinion],
    dimension: str,
) -> dict[str, dict[str, float]]:
    """Break down sentiment scores by a demographic dimension.

    Parameters
    ----------
    opinions:
        Scored opinions with populated demographics.
    dimension:
        One of ``"age_range"``, ``"region"``, ``"employment_status"``,
        ``"income_bracket"``.

    Returns
    -------
    A dict mapping each demographic group to its mean sentiment scores.
    """
    groups: dict[str, list[Opinion]] = defaultdict(list)
    for op in opinions:
        val = getattr(op.demographics, dimension, None)
        if val:
            groups[val].append(op)

    result: dict[str, dict[str, float]] = {}
    for group_name, members in groups.items():
        scored = [m for m in members if m.sentiment_scores]
        if not scored:
            continue
        keys = scored[0].sentiment_scores.keys()
        means = {}
        for key in keys:
            vals = [m.sentiment_scores.get(key, 0.0) for m in scored]
            means[key] = round(sum(vals) / len(vals), 4)
        result[group_name] = means

    logger.info(
        "Demographic breakdown by '%s': %d groups found", dimension, len(result)
    )
    return result


def enrich_clusters_with_demographics(
    clusters: list[ClusterResult],
    opinions: list[Opinion],
) -> list[ClusterResult]:
    """Add demographic breakdown to cluster results using opinion data."""
    opinions_by_cluster: dict[int, list[Opinion]] = defaultdict(list)
    for op in opinions:
        opinions_by_cluster[op.cluster_id].append(op)

    for cluster in clusters:
        members = opinions_by_cluster.get(cluster.cluster_id, [])
        for dim in ("age_range", "region", "employment_status", "income_bracket"):
            breakdown = breakdown_by_demographic(members, dim)
            if breakdown:
                cluster.demographic_breakdown[dim] = {
                    group: scores.get("stance", 0.0)
                    for group, scores in breakdown.items()
                }

    return clusters
