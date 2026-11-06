import pytest
from django.core.exceptions import ImproperlyConfigured
from pydantic import Field
from pydantic import SecretStr

from pydantic_django_settings.base import DjangoSettings
from pydantic_django_settings.loading import SETTINGS_CLASS_ENV
from pydantic_django_settings.loading import load_settings
from pydantic_django_settings.loading import select_settings_class


class Development(DjangoSettings):
    SECRET_KEY: str = "dev"


class Production(DjangoSettings):
    SECRET_KEY: str
    SESSION_COOKIE_AGE: int = 3600
    PORTS: list[int] = []
    database_password: SecretStr = Field(validation_alias="DATABASE_PASSWORD")


CLASSES: list[type[DjangoSettings]] = [Development, Production]
PRODUCTION_ENV = {"DJANGO_SECRET_KEY": "secret", "DATABASE_PASSWORD": "db-secret"}


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (SETTINGS_CLASS_ENV, *PRODUCTION_ENV, "DJANGO_SESSION_COOKIE_AGE", "DJANGO_PORTS"):
        monkeypatch.delenv(name, raising=False)


def test_selector_variable_name() -> None:
    assert SETTINGS_CLASS_ENV == "DJANGO_SETTINGS_CLASS"


def test_selects_the_class_named_by_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SETTINGS_CLASS_ENV, "Production")
    assert select_settings_class(CLASSES) == ("Production", Production)


def test_falls_back_to_the_default_when_unset() -> None:
    assert select_settings_class(CLASSES, default="Development") == ("Development", Development)


def test_the_environment_beats_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SETTINGS_CLASS_ENV, "Production")
    assert select_settings_class(CLASSES, default="Development") == ("Production", Production)


def test_empty_selector_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SETTINGS_CLASS_ENV, "")
    assert select_settings_class(CLASSES, default="Development") == ("Development", Development)


def test_unset_selector_without_default_is_an_error() -> None:
    with pytest.raises(ImproperlyConfigured, match=r"DJANGO_SETTINGS_CLASS is not set.*Development, Production"):
        select_settings_class(CLASSES)


def test_unknown_selector_is_rejected_with_the_valid_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SETTINGS_CLASS_ENV, "Staging")
    with pytest.raises(ImproperlyConfigured, match=r"Unknown DJANGO_SETTINGS_CLASS 'Staging'.*Development, Production"):
        select_settings_class(CLASSES)


def test_unknown_default_is_rejected_too() -> None:
    with pytest.raises(ImproperlyConfigured, match=r"Unknown DJANGO_SETTINGS_CLASS 'Staging'"):
        select_settings_class(CLASSES, default="Staging")


def test_duplicate_class_names_are_a_programming_error() -> None:
    class Shadow(DjangoSettings):
        pass

    Shadow.__name__ = "Development"
    with pytest.raises(ValueError, match="Development"):
        select_settings_class([Development, Shadow], default="Development")


def test_loads_the_class_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in PRODUCTION_ENV.items():
        monkeypatch.setenv(name, value)
    settings = load_settings("Production", Production)
    assert isinstance(settings, Production)
    assert settings.SECRET_KEY == "secret"
    assert settings.database_password.get_secret_value() == "db-secret"


def test_missing_variables_are_reported_by_variable_name() -> None:
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_settings("Production", Production)
    message = str(excinfo.value)
    assert message.startswith("Invalid settings for Production: ")
    assert "DJANGO_SECRET_KEY: Field required" in message
    assert "DATABASE_PASSWORD: Field required" in message


def test_invalid_values_are_reported_by_variable_without_the_value(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in PRODUCTION_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DJANGO_SESSION_COOKIE_AGE", "twelve-hours")
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_settings("Production", Production)
    message = str(excinfo.value)
    assert "DJANGO_SESSION_COOKIE_AGE: Input should be a valid integer" in message
    for value in ("twelve-hours", "secret", "db-secret"):
        assert value not in message
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__


def test_nested_locations_are_appended_to_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in PRODUCTION_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DJANGO_PORTS", '[8000, "http"]')
    with pytest.raises(ImproperlyConfigured, match=r"DJANGO_PORTS\[1\]: Input should be a valid integer"):
        load_settings("Production", Production)


def test_malformed_json_for_a_complex_field_is_reported_like_a_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in PRODUCTION_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DJANGO_PORTS", "8000,8001")
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_settings("Production", Production)
    message = str(excinfo.value)
    assert message.startswith("Invalid settings for Production: DJANGO_PORTS: ")
    assert "JSON" in message
    assert "8000" not in message
    assert excinfo.value.__cause__ is None
