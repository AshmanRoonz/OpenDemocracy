"""X (Twitter) connector — fetches opt-in public posts via the X API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from opendemocracy.input.anonymizer import anonymize_id, strip_pii
from opendemocracy.input.connectors import BaseConnector
from opendemocracy.models import Opinion, SourcePlatform

logger = logging.getLogger(__name__)


@dataclass
class TwitterConfig:
    """Configuration for the X/Twitter connector."""

    bearer_token: str = ""
    min_tweet_length: int = 30
    lang: str = "en"


class TwitterConnector(BaseConnector):
    """Fetch public tweets about a topic from X.

    Requires ``tweepy`` to be installed and a valid bearer token.
    All fetched data is anonymized before being returned.
    """

    def __init__(self, config: TwitterConfig | None = None) -> None:
        self.config = config or TwitterConfig()
        self._client = None

    @property
    def platform_name(self) -> str:
        return "X (Twitter)"

    def _get_client(self):  # type: ignore[no-untyped-def]
        """Lazily initialize the Tweepy client."""
        if self._client is None:
            try:
                import tweepy  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "Install tweepy to use the Twitter connector: pip install tweepy"
                ) from exc
            self._client = tweepy.Client(bearer_token=self.config.bearer_token)
        return self._client

    def fetch_opinions(
        self,
        topic: str,
        *,
        limit: int = 100,
    ) -> list[Opinion]:
        """Search X for tweets about *topic* and return anonymized opinions."""
        client = self._get_client()

        query = f"{topic} lang:{self.config.lang} -is:retweet"
        opinions: list[Opinion] = []
        seen_ids: set[str] = set()

        # Paginate through results (tweepy v2 search)
        paginator = client.search_recent_tweets(
            query=query,
            max_results=min(limit, 100),
            tweet_fields=["created_at", "text"],
        )

        if paginator.data is None:
            logger.warning("No tweets found for topic '%s'", topic)
            return opinions

        for tweet in paginator.data:
            if len(tweet.text) < self.config.min_tweet_length:
                continue

            anon_id = anonymize_id(str(tweet.id), salt="twitter")
            if anon_id in seen_ids:
                continue
            seen_ids.add(anon_id)

            opinions.append(
                Opinion(
                    id=anon_id,
                    text=strip_pii(tweet.text),
                    source=SourcePlatform.TWITTER,
                    topic=topic,
                )
            )

            if len(opinions) >= limit:
                break

        logger.info("Fetched %d opinions from X for topic '%s'", len(opinions), topic)
        return opinions
