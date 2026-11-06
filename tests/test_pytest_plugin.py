import pytest


PROBE = """
import os

def test_probe():
    assert os.environ.get("DJANGO_SETTINGS_CLASS") == {expected!r}
"""


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DJANGO_SETTINGS_CLASS", raising=False)


def test_ini_option_sets_the_selector(pytester: pytest.Pytester) -> None:
    pytester.makeini("[pytest]\nDJANGO_SETTINGS_CLASS = Testing\n")
    pytester.makepyfile(PROBE.format(expected="Testing"))
    pytester.runpytest_subprocess().assert_outcomes(passed=1)


def test_environment_beats_the_ini_option(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_CLASS", "Development")
    pytester.makeini("[pytest]\nDJANGO_SETTINGS_CLASS = Testing\n")
    pytester.makepyfile(PROBE.format(expected="Development"))
    pytester.runpytest_subprocess().assert_outcomes(passed=1)


def test_command_line_option_beats_the_environment(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_CLASS", "Development")
    pytester.makepyfile(PROBE.format(expected="Testing"))
    pytester.runpytest_subprocess("--django-settings-class=Testing").assert_outcomes(passed=1)


def test_leaves_the_environment_alone_when_nothing_is_configured(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(PROBE.format(expected=None))
    pytester.runpytest_subprocess().assert_outcomes(passed=1)


def test_reports_the_source_in_the_header(pytester: pytest.Pytester) -> None:
    pytester.makeini("[pytest]\nDJANGO_SETTINGS_CLASS = Testing\n")
    pytester.makepyfile(PROBE.format(expected="Testing"))
    result = pytester.runpytest_subprocess()
    result.stdout.fnmatch_lines(["settings class: Testing (from ini)"])


def test_reports_the_environment_as_source(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_SETTINGS_CLASS", "Development")
    pytester.makepyfile(PROBE.format(expected="Development"))
    result = pytester.runpytest_subprocess()
    result.stdout.fnmatch_lines(["settings class: Development (from env)"])
