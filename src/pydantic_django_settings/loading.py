import os
import re
from collections.abc import Iterable
from typing import Final

from django.core.exceptions import ImproperlyConfigured
from pydantic import ValidationError
from pydantic_settings import SettingsError

from pydantic_django_settings.base import DjangoSettings


SETTINGS_CLASS_ENV: Final = "DJANGO_SETTINGS_CLASS"
"""The environment variable that names the settings class to load."""


def select_settings_class(
    classes: Iterable[type[DjangoSettings]], *, default: str | None = None
) -> tuple[str, type[DjangoSettings]]:
    """
    Return the name and the class selected by ``DJANGO_SETTINGS_CLASS``, or by ``default`` when the variable is unset.

    An empty variable counts as unset. Unset without a default, or a name that is not among ``classes``, raises
    ``ImproperlyConfigured`` listing the valid names.
    """
    by_name: dict[str, type[DjangoSettings]] = {}
    for cls in classes:
        if cls.__name__ in by_name:
            raise ValueError(f"Duplicate settings class name {cls.__name__!r}: {by_name[cls.__name__]} and {cls}")
        by_name[cls.__name__] = cls
    choices = ", ".join(by_name)
    name = os.environ.get(SETTINGS_CLASS_ENV) or default
    if not name:
        raise ImproperlyConfigured(f"{SETTINGS_CLASS_ENV} is not set; choose one of: {choices}")
    try:
        return name, by_name[name]
    except KeyError:
        raise ImproperlyConfigured(f"Unknown {SETTINGS_CLASS_ENV} {name!r}; choose one of: {choices}") from None


def environment_variable(cls: type[DjangoSettings], loc: tuple[int | str, ...]) -> str:
    """
    Return the environment variable behind a validation error location.

    pydantic reports an aliased field by its alias, which is the variable name as is, and any other field by its name,
    which carries the ``env_prefix``. Nested locations, e.g. an item of a list, are appended in brackets.
    """
    name = str(loc[0])
    field = cls.model_fields.get(name)
    if field is not None and field.validation_alias is None:
        name = str(cls.model_config.get("env_prefix", "")) + name
    return name + "".join(f"[{part}]" for part in loc[1:])


def load_settings(name: str, cls: type[DjangoSettings]) -> DjangoSettings:
    """
    Instantiate the settings class from the environment.

    A validation failure raises ``ImproperlyConfigured`` naming the environment variables and the problems only. The
    pydantic error is deliberately not chained, because its message echoes the input values, which include secrets.
    """
    try:
        return cls()
    except ValidationError as error:
        problems = "; ".join(
            f"{environment_variable(cls, e['loc'])}: {e['msg']}" for e in error.errors(include_input=False)
        )
        raise ImproperlyConfigured(f"Invalid settings for {name}: {problems}") from None
    except SettingsError as error:
        # pydantic-settings parses list, dict and model fields as JSON before validation and reports malformed JSON
        # as a SettingsError naming the field, e.g. 'error parsing value for field "PORTS" from source
        # "EnvSettingsSource"'. Report it like a validation problem, by the variable, without the value.
        match = re.search(r'field "([^"]+)"', str(error))
        variable = environment_variable(cls, (match.group(1),)) if match else "?"
        raise ImproperlyConfigured(f"Invalid settings for {name}: {variable}: value is not valid JSON") from None
