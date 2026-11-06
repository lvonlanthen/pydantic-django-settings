"""
pytest plugin that sets ``DJANGO_SETTINGS_CLASS`` before pytest-django loads the settings.

The settings class comes from the ``--django-settings-class`` option, else the environment, else the
``DJANGO_SETTINGS_CLASS`` ini option, the same precedence pytest-django applies to ``DJANGO_SETTINGS_MODULE``.
The plugin is registered through the ``pytest11`` entry point, so it is active whenever the package is installed.
"""

import os

import pytest

from pydantic_django_settings.loading import SETTINGS_CLASS_ENV


OPTION = "--django-settings-class"
_source_key = pytest.StashKey[str]()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addini(SETTINGS_CLASS_ENV, f"The settings class to run the tests under ({SETTINGS_CLASS_ENV}).")
    parser.addoption(
        OPTION,
        dest="django_settings_class",
        default=None,
        help=f"The settings class to run the tests under; overrides {SETTINGS_CLASS_ENV}.",
    )


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests(early_config: pytest.Config, parser: pytest.Parser, args: list[str]) -> None:
    option = parser.parse_known_args(args).django_settings_class
    if option:
        value, source = option, "option"
    elif os.environ.get(SETTINGS_CLASS_ENV):
        value, source = os.environ[SETTINGS_CLASS_ENV], "env"
    elif early_config.getini(SETTINGS_CLASS_ENV):
        value, source = early_config.getini(SETTINGS_CLASS_ENV), "ini"
    else:
        return
    os.environ[SETTINGS_CLASS_ENV] = value
    early_config.stash[_source_key] = f"settings class: {value} (from {source})"


def pytest_report_header(config: pytest.Config) -> list[str]:
    return [config.stash[_source_key]] if _source_key in config.stash else []
