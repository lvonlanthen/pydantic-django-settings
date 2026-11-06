import pytest
from pydantic import ValidationError

from pydantic_django_settings.base import CommaSeparatedList
from pydantic_django_settings.base import DjangoSettings


class Settings(DjangoSettings):
    SECRET_KEY: str = "default"
    DEBUG_TOOLBAR: bool = False
    ALLOWED_HOSTS: CommaSeparatedList = []


def test_fields_are_read_with_the_django_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SECRET_KEY", "from-env")
    assert Settings().SECRET_KEY == "from-env"


def test_variable_names_are_case_sensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_SECRET_KEY", raising=False)
    monkeypatch.setenv("django_secret_key", "from-env")
    assert Settings().SECRET_KEY == "default"


def test_empty_variables_count_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_DEBUG_TOOLBAR", "")
    assert Settings().DEBUG_TOOLBAR is False


def test_wrong_values_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_DEBUG_TOOLBAR", "maybe")
    with pytest.raises(ValidationError):
        Settings()


def test_comma_separated_list_splits_strips_and_drops_empty_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", " a.example.ch, ,b.example.ch ")
    assert Settings().ALLOWED_HOSTS == ["a.example.ch", "b.example.ch"]


def test_comma_separated_list_default_is_used_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_ALLOWED_HOSTS", raising=False)
    assert Settings().ALLOWED_HOSTS == []


def test_comma_separated_list_accepts_a_list_given_directly() -> None:
    assert Settings(ALLOWED_HOSTS=["x.example.ch"]).ALLOWED_HOSTS == ["x.example.ch"]


def test_post_setup_is_a_no_op() -> None:
    DjangoSettings().post_setup()
