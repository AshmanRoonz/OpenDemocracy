"""UBI Pilot runner — end-to-end pipeline from input to report.

Can run in two modes:
  1. **Live mode**: Fetches real data from Reddit/X (requires API keys).
  2. **Demo mode**: Uses synthetic data to demonstrate the full pipeline
     without any external dependencies.

Usage::

    python -m opendemocracy.pilot.runner          # demo mode
    python -m opendemocracy.pilot.runner --live    # live mode (needs API keys)
"""

from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import datetime, timedelta

from opendemocracy.modeling.scenarios import generate_scenarios
from opendemocracy.models import Demographics, Opinion, PilotReport, SourcePlatform
from opendemocracy.output.reports import generate_report
from opendemocracy.pilot.ubi_config import ALL_SCENARIOS, TOPIC
from opendemocracy.processing.bias import detect_bias
from opendemocracy.processing.clustering import cluster_opinions
from opendemocracy.processing.sentiment import score_opinions

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthetic data for demo mode
# ---------------------------------------------------------------------------

_PRO_UBI = [
    "UBI would give people the freedom to pursue education and start businesses "
    "without fear of destitution. The Finnish pilot showed reduced stress and "
    "improved wellbeing with minimal labor market impact.",
    "Automation is eliminating jobs faster than we can create them. A basic "
    "income is the only realistic safety net for the 21st century economy.",
    "I support UBI because it removes the bureaucratic overhead of means-tested "
    "welfare. Just give people cash and let them decide how to use it.",
    "As a small business owner, I think UBI would be great for entrepreneurship. "
    "People could take risks knowing they won't starve if they fail.",
    "The Stockton pilot proved it works. People used the money for essentials, "
    "found better jobs, and their mental health improved dramatically.",
    "We should support universal basic income now. Poverty is a policy choice "
    "and this is the most effective solution we have evidence for.",
    "I'm in favor of UBI. It would help caregivers, artists, volunteers — people "
    "who do essential work that the market doesn't compensate.",
]

_ANTI_UBI = [
    "UBI is fiscally irresponsible. The cost would be enormous and the money "
    "would be better spent on targeted programs for those who actually need help.",
    "I oppose UBI because it would cause significant inflation. If everyone gets "
    "more money, prices just go up and we're back where we started.",
    "Giving people free money discourages work. We need programs that help people "
    "develop skills and find employment, not handouts.",
    "UBI is a terrible idea. The pilots were too small and short to prove anything. "
    "Scaling to a whole country would be completely different.",
    "The fiscal cost of UBI would be dangerous. We'd either need massive tax "
    "increases or unsustainable debt. Neither is acceptable.",
    "I'm against UBI. It doesn't address the root causes of poverty like lack of "
    "education, healthcare, and affordable housing.",
]

_NEUTRAL_UBI = [
    "I can see arguments on both sides. UBI might reduce poverty but the cost "
    "concerns are legitimate. Maybe a negative income tax would be better?",
    "Interesting concept but I'm not sure it would work at scale. The pilots "
    "showed mixed results depending on how you measure success.",
    "I think the debate about UBI is more nuanced than either side admits. "
    "It depends entirely on the implementation details and funding mechanism.",
    "Not sure where I stand on UBI. The evidence from pilots is promising but "
    "limited. We need larger, longer experiments before deciding.",
]

_DEMO_SOURCES = [SourcePlatform.REDDIT, SourcePlatform.TWITTER, SourcePlatform.SURVEY]
_AGE_RANGES = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
_REGIONS = ["US-Northeast", "US-South", "US-Midwest", "US-West", "EU-West", "EU-North"]
_EMPLOYMENT = ["employed", "unemployed", "self-employed", "student", "retired"]
_INCOME = ["low", "lower-middle", "middle", "upper-middle", "high"]


def _generate_synthetic_opinions(n: int = 80) -> list[Opinion]:
    """Generate a set of synthetic opinions for demo purposes."""
    rng = random.Random(42)
    opinions: list[Opinion] = []
    base_time = datetime(2025, 6, 1)

    all_texts = (
        [(t, "pro") for t in _PRO_UBI]
        + [(t, "anti") for t in _ANTI_UBI]
        + [(t, "neutral") for t in _NEUTRAL_UBI]
    )

    for i in range(n):
        text, _ = rng.choice(all_texts)
        # Add slight variation
        if rng.random() > 0.5:
            text = text + " " + rng.choice([
                "This is an important issue.",
                "We need more research on this.",
                "The data is clear on this point.",
                "I've changed my mind on this over time.",
                "My experience confirms this view.",
            ])

        opinions.append(
            Opinion(
                text=text,
                source=rng.choice(_DEMO_SOURCES),
                topic=TOPIC,
                timestamp=base_time + timedelta(hours=rng.randint(0, 720)),
                demographics=Demographics(
                    age_range=rng.choice(_AGE_RANGES),
                    region=rng.choice(_REGIONS),
                    employment_status=rng.choice(_EMPLOYMENT),
                    income_bracket=rng.choice(_INCOME),
                ),
            )
        )

    return opinions


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def run_pipeline(opinions: list[Opinion]) -> PilotReport:
    """Run the full analysis pipeline on a set of opinions."""
    logger.info("Starting pipeline with %d opinions", len(opinions))

    # 1. Bias detection
    bias_warnings = detect_bias(opinions)

    # 2. Sentiment scoring
    score_opinions(opinions)

    # 3. Generate simple embeddings from sentiment scores for clustering
    #    (In production, use EmbeddingPipeline with sentence-transformers)
    for op in opinions:
        scores = op.sentiment_scores
        op.embedding = [
            scores.get("stance", 0.0),
            scores.get("urgency", 0.0),
            scores.get("certainty", 0.0),
            scores.get("intensity", 0.0),
        ]

    # 4. Cluster opinions
    clusters = cluster_opinions(opinions, n_clusters=4)

    # 5. Run scenario modeling
    scenarios = generate_scenarios(ALL_SCENARIOS)

    # 6. Build report
    report = PilotReport(
        topic=TOPIC,
        total_opinions=len(opinions),
        clusters=clusters,
        scenarios=scenarios,
        bias_warnings=bias_warnings,
        methodology_notes=[
            "Sentiment scored using lexicon-based multi-dimensional analysis",
            "Clustering performed using K-Means on sentiment feature vectors",
            "Impact projections use declared parametric models (see ARCHITECTURE.md)",
            "All assumptions are stated explicitly in each scenario",
            "Demo mode: synthetic data used for illustration",
        ],
    )

    return report


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run the OpenDemocracy UBI pilot analysis"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Fetch real data from Reddit/X (requires API keys in environment)",
    )
    parser.add_argument(
        "-n",
        type=int,
        default=80,
        help="Number of opinions to analyze (default: 80)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output file for the report (default: stdout)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.live:
        # Live mode — fetch from platforms
        import os

        opinions: list[Opinion] = []

        reddit_id = os.environ.get("REDDIT_CLIENT_ID")
        if reddit_id:
            from opendemocracy.input.connectors.reddit import RedditConfig, RedditConnector

            connector = RedditConnector(
                RedditConfig(
                    client_id=reddit_id,
                    client_secret=os.environ.get("REDDIT_CLIENT_SECRET", ""),
                )
            )
            opinions.extend(connector.fetch_opinions(TOPIC, limit=args.n))
            logger.info("Fetched %d opinions from Reddit", len(opinions))
        else:
            logger.warning("REDDIT_CLIENT_ID not set — skipping Reddit")

        twitter_token = os.environ.get("TWITTER_BEARER_TOKEN")
        if twitter_token:
            from opendemocracy.input.connectors.twitter import TwitterConfig, TwitterConnector

            connector_tw = TwitterConnector(TwitterConfig(bearer_token=twitter_token))
            opinions.extend(connector_tw.fetch_opinions(TOPIC, limit=args.n))
            logger.info("Fetched %d total opinions after X", len(opinions))
        else:
            logger.warning("TWITTER_BEARER_TOKEN not set — skipping X")

        if not opinions:
            logger.error("No data fetched. Set API keys or run without --live for demo mode.")
            sys.exit(1)
    else:
        # Demo mode
        opinions = _generate_synthetic_opinions(args.n)
        logger.info("Generated %d synthetic opinions for demo", len(opinions))

    report = run_pipeline(opinions)
    markdown = generate_report(report)

    if args.output:
        with open(args.output, "w") as f:
            f.write(markdown)
        logger.info("Report written to %s", args.output)
    else:
        print(markdown)


if __name__ == "__main__":
    main()
