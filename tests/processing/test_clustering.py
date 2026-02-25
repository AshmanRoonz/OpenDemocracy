"""Tests for opinion clustering."""

from opendemocracy.models import Opinion
from opendemocracy.processing.clustering import cluster_opinions


def _make_opinions_with_embeddings(n: int = 20) -> list[Opinion]:
    """Create opinions with simple 4-d embeddings in two distinct groups."""
    opinions = []
    for i in range(n):
        if i < n // 2:
            # Pro cluster
            emb = [0.8, 0.1, 0.5, 0.2]
            text = "I support this policy"
        else:
            # Anti cluster
            emb = [-0.8, 0.1, 0.3, 0.1]
            text = "I oppose this policy"
        op = Opinion(text=text, embedding=emb)
        op.sentiment_scores = {"stance": emb[0], "urgency": emb[1], "certainty": emb[2], "intensity": emb[3]}
        opinions.append(op)
    return opinions


class TestClusterOpinions:
    def test_returns_clusters(self) -> None:
        opinions = _make_opinions_with_embeddings(20)
        clusters = cluster_opinions(opinions, n_clusters=2)
        assert len(clusters) >= 1

    def test_all_opinions_assigned(self) -> None:
        opinions = _make_opinions_with_embeddings(20)
        cluster_opinions(opinions, n_clusters=2)
        assert all(op.cluster_id >= 0 for op in opinions)

    def test_cluster_has_size(self) -> None:
        opinions = _make_opinions_with_embeddings(20)
        clusters = cluster_opinions(opinions, n_clusters=2)
        total = sum(c.size for c in clusters)
        assert total == 20

    def test_cluster_has_stance_distribution(self) -> None:
        opinions = _make_opinions_with_embeddings(20)
        clusters = cluster_opinions(opinions, n_clusters=2)
        for c in clusters:
            if c.stance_distribution:
                assert "support" in c.stance_distribution
                assert "oppose" in c.stance_distribution
