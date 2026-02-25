"""Verify the package is importable and version is set."""


def test_version() -> None:
    import opendemocracy

    assert opendemocracy.__version__ == "0.1.0"


def test_subpackages_importable() -> None:
    import opendemocracy.input
    import opendemocracy.modeling
    import opendemocracy.output
    import opendemocracy.processing

    assert opendemocracy.input is not None
    assert opendemocracy.processing is not None
    assert opendemocracy.modeling is not None
    assert opendemocracy.output is not None
