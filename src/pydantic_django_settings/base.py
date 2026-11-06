from typing import Annotated
from typing import Any

from pydantic import BeforeValidator
from pydantic_settings import BaseSettings
from pydantic_settings import NoDecode
from pydantic_settings import SettingsConfigDict


def split_comma_separated(value: Any) -> Any:
    """Split a comma separated string into its stripped, non-empty items; pass anything else through."""
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


CommaSeparatedList = Annotated[list[str], NoDecode, BeforeValidator(split_comma_separated)]
"""A list setting given as a comma separated string in the environment, where pydantic-settings would expect JSON."""


class DjangoSettings(BaseSettings):
    """
    Base class of every settings class.

    Every uppercase attribute is exported as a Django setting by ``setup``. There are three kinds:

    - ``ClassVar`` attributes are fixed per settings class and cannot be changed through the environment.
    - pydantic fields are read from the environment, through ``DJANGO_<FIELD>`` unless the field has a
      ``validation_alias``. Variable names are case sensitive, an empty variable counts as unset, and values are
      validated against the field type, so a wrong value aborts the startup instead of being ignored.
    - properties compute a setting from other attributes.

    Lowercase attributes are inputs for computed settings and are not exported.
    """

    model_config = SettingsConfigDict(env_prefix="DJANGO_", case_sensitive=True, env_ignore_empty=True)

    def post_setup(self) -> None:
        """Hook that runs once the settings have been exported to Django, e.g. to initialise external SDKs."""
