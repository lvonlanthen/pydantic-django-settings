from importlib.metadata import version


def test_version() -> None:
    assert version("pydantic-django-settings") == "0.1.0"
