"""
Define Django settings as pydantic-settings classes, one per environment, selected by ``DJANGO_SETTINGS_CLASS``.

A project's settings package defines its settings classes and ends with::

    setup(globals(), [Development, Production, Testing], default="Development")

which selects the class named by ``DJANGO_SETTINGS_CLASS``, instantiates it from the environment and exports its
uppercase attributes into the module, which is all Django expects from ``DJANGO_SETTINGS_MODULE``.
"""

from collections.abc import Iterable
from collections.abc import MutableMapping
from typing import Any

from pydantic_django_settings.base import CommaSeparatedList
from pydantic_django_settings.base import DjangoSettings
from pydantic_django_settings.base import split_comma_separated
from pydantic_django_settings.export import django_settings
from pydantic_django_settings.loading import SETTINGS_CLASS_ENV
from pydantic_django_settings.loading import load_settings
from pydantic_django_settings.loading import select_settings_class


__all__ = ["SETTINGS_CLASS_ENV", "CommaSeparatedList", "DjangoSettings", "setup", "split_comma_separated"]


def setup(
    namespace: MutableMapping[str, Any],
    classes: Iterable[type[DjangoSettings]],
    *,
    default: str | None = None,
) -> DjangoSettings:
    """
    Load the settings class selected by ``DJANGO_SETTINGS_CLASS`` and export it into ``namespace``.

    ``namespace`` is the ``globals()`` of the settings module. ``classes`` are the selectable settings classes and
    ``default`` is the name used when the variable is unset. The uppercase attributes of the instance become module
    globals, ``SETTINGS_CLASS`` is set to the selected name, ``post_setup`` runs and the instance is returned.
    """
    name, cls = select_settings_class(classes, default=default)
    settings = load_settings(name, cls)
    namespace.update(django_settings(settings, name))
    settings.post_setup()
    return settings
