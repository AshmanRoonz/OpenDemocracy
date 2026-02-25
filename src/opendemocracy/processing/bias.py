"""Bias detection — flag sampling bias, framing effects, and manipulation.

Runs on every processing step to surface data-quality issues before they
contaminate downstream analysis.
"""

from __future__ import annotations

import logging
from collections import Counter

from opendemocracy.models import Opinion, SourcePlatform

logger = logging.getLogger(__name__)

# Thresholds (configurable in a real deployment)
_MIN_OPINIONS = 30
_SOURCE_DOMINANCE_THRESHOLD = 0.80
_DEMO_COVERAGE_THRESHOLD = 0.10
_DUPLICATE_TEXT_THRESHOLD = 0.05


def detect_bias(opinions: list[Opinion]) -> list[str]:
    """Run bias checks on a collection of opinions and return warnings."""
    warnings: list[str] = []

    warnings.extend(_check_sample_size(opinions))
    warnings.extend(_check_source_diversity(opinions))
    warnings.extend(_check_demographic_coverage(opinions))
    warnings.extend(_check_duplicate_content(opinions))
    warnings.extend(_check_temporal_clustering(opinions))

    if warnings:
        logger.warning("Bias detection found %d warnings", len(warnings))
    else:
        logger.info("Bias detection: no issues found")

    return warnings


def _check_sample_size(opinions: list[Opinion]) -> list[str]:
    """Warn if sample is too small for meaningful analysis."""
    if len(opinions) < _MIN_OPINIONS:
        return [
            f"Small sample size ({len(opinions)} opinions). "
            f"Minimum recommended is {_MIN_OPINIONS}. "
            "Results may not be representative."
        ]
    return []


def _check_source_diversity(opinions: list[Opinion]) -> list[str]:
    """Warn if one platform dominates the input."""
    source_counts = Counter(op.source for op in opinions)
    total = len(opinions)
    warnings: list[str] = []

    for source, count in source_counts.items():
        ratio = count / total
        if ratio > _SOURCE_DOMINANCE_THRESHOLD and len(source_counts) > 1:
            warnings.append(
                f"Source bias: {source.value} accounts for {ratio:.0%} of opinions. "
                f"This platform's user demographics will skew results."
            )

    if len(source_counts) == 1:
        only = list(source_counts.keys())[0]
        warnings.append(
            f"Single-source data (all from {only.value}). "
            "Cross-platform collection recommended for representativeness."
        )

    return warnings


def _check_demographic_coverage(opinions: list[Opinion]) -> list[str]:
    """Warn if demographic data is sparse."""
    with_demo = sum(
        1
        for op in opinions
        if op.demographics.age_range or op.demographics.region
    )
    if not opinions:
        return []
    ratio = with_demo / len(opinions)
    if ratio < _DEMO_COVERAGE_THRESHOLD:
        return [
            f"Low demographic coverage ({ratio:.0%} of opinions have demographic data). "
            "Demographic breakdowns will have limited reliability."
        ]
    return []


def _check_duplicate_content(opinions: list[Opinion]) -> list[str]:
    """Detect copy-paste or bot-generated duplicate text."""
    texts = [op.text.strip().lower() for op in opinions]
    text_counts = Counter(texts)
    total = len(texts)
    duplicates = sum(count - 1 for count in text_counts.values() if count > 1)

    if total > 0 and duplicates / total > _DUPLICATE_TEXT_THRESHOLD:
        return [
            f"Duplicate content detected: {duplicates} duplicate opinions "
            f"({duplicates / total:.0%} of total). Possible bot activity or "
            "coordinated campaign."
        ]
    return []


def _check_temporal_clustering(opinions: list[Opinion]) -> list[str]:
    """Warn if opinions cluster suspiciously in time (brigading signal)."""
    timestamps = sorted(op.timestamp for op in opinions)
    if len(timestamps) < 10:
        return []

    # Check if >50% arrived in a window that's <10% of the total time span
    total_span = (timestamps[-1] - timestamps[0]).total_seconds()
    if total_span == 0:
        return [
            "All opinions have identical timestamps. "
            "Possible data import artifact or coordinated submission."
        ]

    window_size = max(int(len(timestamps) * 0.1), 1)
    for i in range(len(timestamps) - window_size):
        window_span = (timestamps[i + window_size] - timestamps[i]).total_seconds()
        if window_span < total_span * 0.05 and window_size > len(timestamps) * 0.5:
            return [
                "Temporal clustering detected: a large burst of opinions arrived "
                "in a very short window. Possible brigading or coordinated campaign."
            ]

    return []
