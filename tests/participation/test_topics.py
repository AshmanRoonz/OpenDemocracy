"""Tests for topic management."""

from datetime import datetime, timedelta, timezone

import pytest

from opendemocracy.models import Topic
from opendemocracy.participation.topics import TopicStore


class TestTopicStore:
    def test_create_and_get(self) -> None:
        store = TopicStore()
        topic = Topic(id="t1", title="UBI", description="Should we implement UBI?")
        store.create(topic)
        assert store.get("t1") is topic

    def test_get_missing_returns_none(self) -> None:
        store = TopicStore()
        assert store.get("nope") is None

    def test_duplicate_id_raises(self) -> None:
        store = TopicStore()
        store.create(Topic(id="t1", title="A"))
        with pytest.raises(RuntimeError, match="already exists"):
            store.create(Topic(id="t1", title="B"))

    def test_open_ended_topic_is_open(self) -> None:
        store = TopicStore()
        store.create(Topic(id="t1", title="A", closes_at=None))
        assert store.is_open("t1") is True

    def test_future_close_is_open(self) -> None:
        store = TopicStore()
        future = datetime.now(tz=timezone.utc) + timedelta(days=7)
        store.create(Topic(id="t1", title="A", closes_at=future))
        assert store.is_open("t1") is True

    def test_past_close_is_closed(self) -> None:
        store = TopicStore()
        past = datetime.now(tz=timezone.utc) - timedelta(days=1)
        store.create(Topic(id="t1", title="A", closes_at=past))
        assert store.is_open("t1") is False

    def test_nonexistent_topic_not_open(self) -> None:
        store = TopicStore()
        assert store.is_open("nothing") is False

    def test_list_open(self) -> None:
        store = TopicStore()
        past = datetime.now(tz=timezone.utc) - timedelta(days=1)
        store.create(Topic(id="open1", title="Open"))
        store.create(Topic(id="closed1", title="Closed", closes_at=past))
        assert len(store.list_open()) == 1
        assert store.list_open()[0].id == "open1"

    def test_count(self) -> None:
        store = TopicStore()
        assert store.count == 0
        store.create(Topic(id="a", title="A"))
        store.create(Topic(id="b", title="B"))
        assert store.count == 2
