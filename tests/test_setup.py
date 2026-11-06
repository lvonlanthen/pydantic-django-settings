import importlib
import sys
from collections.abc import Iterator
from typing import Any

import pytest
from django.conf import Settings
from django.core.exceptions import ImproperlyConfigured

from pydantic_django_settings import DjangoSettings
from pydantic_django_settings import setup


class Development(DjangoSettings):
    SECRET_KEY: str = "dev"


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DJANGO_SETTINGS_CLASS", "DJANGO_SECRET_KEY", "DJANGO_ALLOWED_HOSTS", "DATABASE_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def example_project() -> Iterator[None]:
    modules = [name for name in sys.modules if name.startswith("example_project")]
    for name in modules:
        del sys.modules[name]
    yield
    for name in [name for name in sys.modules if name.startswith("example_project")]:
        del sys.modules[name]


def test_exports_into_the_namespace_and_returns_the_instance() -> None:
    namespace: dict[str, Any] = {}
    settings = setup(namespace, [Development], default="Development")
    assert isinstance(settings, Development)
    assert namespace["SETTINGS_CLASS"] == "Development"
    assert namespace["SECRET_KEY"] == "dev"


def test_runs_post_setup_once_after_the_export() -> None:
    namespace: dict[str, Any] = {}
    seen: list[dict[str, Any]] = []

    class WithHook(Development):
        def post_setup(self) -> None:
            seen.append(dict(namespace))

    setup(namespace, [WithHook], default="WithHook")
    assert len(seen) == 1
    assert seen[0]["SECRET_KEY"] == "dev"


def test_selection_errors_propagate() -> None:
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SETTINGS_CLASS is not set"):
        setup({}, [Development])


def test_example_project_loads_as_a_django_settings_module(
    monkeypatch: pytest.MonkeyPatch, example_project: None
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_CLASS", "Production")
    monkeypatch.setenv("DJANGO_SECRET_KEY", "prod")
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "example.ch")
    monkeypatch.setenv("DATABASE_PASSWORD", "pw")
    settings: Any = Settings("example_project.settings")
    assert settings.DEBUG is False
    assert settings.SECRET_KEY == "prod"
    assert settings.ALLOWED_HOSTS == ["example.ch"]
    assert settings.DATABASES["default"]["PASSWORD"] == "pw"
    assert settings.SETTINGS_CLASS == "Production"
    assert settings.INSTALLED_APPS == ["django.contrib.contenttypes"]


def test_example_project_falls_back_to_development(example_project: None) -> None:
    module = importlib.import_module("example_project.settings")
    assert module.SETTINGS_CLASS == "Development"
    assert module.DEBUG is True
    assert module.SECRET_KEY == "dev"


def test_example_project_rejects_an_invalid_production_environment(
    monkeypatch: pytest.MonkeyPatch, example_project: None
) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_CLASS", "Production")
    with pytest.raises(ImproperlyConfigured, match=r"DJANGO_SECRET_KEY: Field required.*DJANGO_ALLOWED_HOSTS"):
        importlib.import_module("example_project.settings")
