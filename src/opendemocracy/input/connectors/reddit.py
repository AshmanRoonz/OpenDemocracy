"""Reddit connector — fetches opt-in public posts via the Reddit API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from opendemocracy.input.anonymizer import anonymize_id, strip_pii
from opendemocracy.input.connectors import BaseConnector
from opendemocracy.models import Opinion, SourcePlatform

logger = logging.getLogger(__name__)

# Subreddits likely to contain policy discussion
DEFAULT_SUBREDDITS = [
    "economics",
    "BasicIncome",
    "PoliticalDiscussion",
    "NeutralPolitics",
    "AskEconomics",
]


@dataclass
class RedditConfig:
    """Configuration for the Reddit connector."""

    client_id: str = ""
    client_secret: str = ""
    user_agent: str = "OpenDemocracy/0.1"
    subreddits: list[str] | None = None
    min_comment_length: int = 50


class RedditConnector(BaseConnector):
    """Fetch public Reddit comments about a topic.

    Requires ``praw`` to be installed and valid Reddit API credentials.
    All fetched data is anonymized before being returned.
    """

    def __init__(self, config: RedditConfig | None = None) -> None:
        self.config = config or RedditConfig()
        self._reddit = None

    @property
    def platform_name(self) -> str:
        return "Reddit"

    def _get_client(self):  # type: ignore[no-untyped-def]
        """Lazily initialize the PRAW Reddit client."""
        if self._reddit is None:
            try:
                import praw  # type: ignore[import-untyped]
            except ImportError as exc:
                raise ImportError(
                    "Install praw to use the Reddit connector: pip install praw"
                ) from exc
            self._reddit = praw.Reddit(
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
                user_agent=self.config.user_agent,
            )
        return self._reddit

    def fetch_opinions(
        self,
        topic: str,
        *,
        limit: int = 100,
    ) -> list[Opinion]:
        """Search Reddit for comments about *topic* and return anonymized opinions."""
        reddit = self._get_client()
        subreddits = self.config.subreddits or DEFAULT_SUBREDDITS
        sub_str = "+".join(subreddits)
        subreddit = reddit.subreddit(sub_str)

        opinions: list[Opinion] = []
        seen_ids: set[str] = set()

        for submission in subreddit.search(topic, sort="relevance", limit=limit):
            submission.comments.replace_more(limit=0)
            for comment in submission.comments.list():
                if len(comment.body) < self.config.min_comment_length:
                    continue

                anon_id = anonymize_id(comment.id, salt="reddit")
                if anon_id in seen_ids:
                    continue
                seen_ids.add(anon_id)

                opinions.append(
                    Opinion(
                        id=anon_id,
                        text=strip_pii(comment.body),
                        source=SourcePlatform.REDDIT,
                        topic=topic,
                    )
                )

                if len(opinions) >= limit:
                    break
            if len(opinions) >= limit:
                break

        logger.info("Fetched %d opinions from Reddit for topic '%s'", len(opinions), topic)
        return opinions
