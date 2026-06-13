"""Topic management for participatory submissions."""

from __future__ import annotations

from datetime import UTC, datetime

from opendemocracy.models import Topic
from opendemocracy.participation.relevance import Interests, rank_topics


class TopicStore:
    """In-memory store for topics.

    In production this would be backed by a database.  The interface stays
    the same.
    """

    def __init__(self) -> None:
        self._topics: dict[str, Topic] = {}

    def create(self, topic: Topic) -> Topic:
        """Register a new topic."""
        if topic.id in self._topics:
            raise RuntimeError(f"Topic {topic.id!r} already exists")
        self._topics[topic.id] = topic
        return topic

    def get(self, topic_id: str) -> Topic | None:
        """Retrieve a topic by ID."""
        return self._topics.get(topic_id)

    def is_open(self, topic_id: str) -> bool:
        """Check whether a topic is currently accepting submissions."""
        topic = self._topics.get(topic_id)
        if topic is None:
            return False
        if topic.closes_at is None:
            return True
        now = datetime.now(tz=UTC)
        closes = topic.closes_at.replace(tzinfo=UTC)
        return now < closes

    def list_open(self) -> list[Topic]:
        """Return all topics that are currently accepting submissions."""
        return [t for t in self._topics.values() if self.is_open(t.id)]

    def list_live(
        self,
        interests: Interests | None = None,
        submission_counts: dict[str, int] | None = None,
    ) -> list[Topic]:
        """Return open topics ordered for the *live issues* feed.

        Topics are ranked by relevance to the citizen's ``interests``, how soon
        they close, and how much activity they're attracting — so the issues
        that matter to a given voice, right now, surface first. See
        :mod:`opendemocracy.participation.relevance`.
        """
        return rank_topics(
            self.list_open(),
            interests or Interests(),
            submission_counts,
        )

    @property
    def count(self) -> int:
        """Total number of topics."""
        return len(self._topics)
