"""Tests for multi-dimensional sentiment analysis."""

from opendemocracy.models import Opinion
from opendemocracy.processing.sentiment import score_opinion, score_opinions


class TestScoreOpinion:
    def test_pro_text_positive_stance(self) -> None:
        op = Opinion(text="I strongly support UBI, it would benefit everyone and help the economy")
        score_opinion(op)
        assert op.sentiment_scores["stance"] > 0

    def test_anti_text_negative_stance(self) -> None:
        op = Opinion(text="I oppose UBI, it would be harmful and a terrible waste of money")
        score_opinion(op)
        assert op.sentiment_scores["stance"] < 0

    def test_neutral_text_near_zero_stance(self) -> None:
        op = Opinion(text="There are arguments on both sides of the UBI discussion")
        score_opinion(op)
        assert abs(op.sentiment_scores["stance"]) < 0.2

    def test_urgent_text_high_urgency(self) -> None:
        op = Opinion(text="We need UBI now! This is urgent, a crisis that is overdue")
        score_opinion(op)
        assert op.sentiment_scores["urgency"] > 0.1

    def test_all_dimensions_present(self) -> None:
        op = Opinion(text="I think UBI is an interesting concept worth studying")
        score_opinion(op)
        assert "stance" in op.sentiment_scores
        assert "urgency" in op.sentiment_scores
        assert "certainty" in op.sentiment_scores
        assert "intensity" in op.sentiment_scores

    def test_intensity_from_caps_and_exclamation(self) -> None:
        op = Opinion(text="THIS IS AMAZING! WE NEED THIS NOW!!!")
        score_opinion(op)
        assert op.sentiment_scores["intensity"] > 0.1


class TestScoreOpinions:
    def test_batch_scoring(self) -> None:
        opinions = [
            Opinion(text="I support this idea"),
            Opinion(text="I oppose this idea"),
            Opinion(text="Not sure about this"),
        ]
        result = score_opinions(opinions)
        assert len(result) == 3
        assert all(op.sentiment_scores for op in result)
