"""Tests for bias detection."""

from opendemocracy.models import Demographics, Opinion, SourcePlatform
from opendemocracy.processing.bias import detect_bias


def _make_opinions(n: int, source: SourcePlatform = SourcePlatform.REDDIT) -> list[Opinion]:
    return [
        Opinion(
            text=f"Opinion number {i} about universal basic income policy discussion",
            source=source,
        )
        for i in range(n)
    ]


class TestDetectBias:
    def test_small_sample_warning(self) -> None:
        opinions = _make_opinions(5)
        warnings = detect_bias(opinions)
        assert any("Small sample" in w for w in warnings)

    def test_single_source_warning(self) -> None:
        opinions = _make_opinions(50)
        warnings = detect_bias(opinions)
        assert any("Single-source" in w for w in warnings)

    def test_no_warnings_for_good_data(self) -> None:
        opinions = []
        for i in range(40):
            opinions.append(
                Opinion(
                    text=f"Unique opinion {i} about policy that is different from others",
                    source=SourcePlatform.REDDIT if i % 2 == 0 else SourcePlatform.TWITTER,
                    demographics=Demographics(age_range="25-34", region="US-West"),
                )
            )
        warnings = detect_bias(opinions)
        # Should have no critical warnings (may still have minor ones)
        assert not any("Small sample" in w for w in warnings)
        assert not any("Single-source" in w for w in warnings)

    def test_duplicate_content_warning(self) -> None:
        # All identical text
        opinions = [
            Opinion(text="exact same text about UBI", source=SourcePlatform.REDDIT)
            for _ in range(50)
        ]
        warnings = detect_bias(opinions)
        assert any("Duplicate" in w for w in warnings)
