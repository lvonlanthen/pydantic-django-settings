from typing import Any

from pydantic import Secret
from pydantic import SecretBytes
from pydantic import SecretStr

from pydantic_django_settings.base import DjangoSettings


# SecretStr and SecretBytes do not inherit from the generic Secret, they only share a private base class.
SECRET_TYPES = (Secret, SecretStr, SecretBytes)


def unwrap_secrets(value: Any) -> Any:
    """Return the value with every pydantic secret replaced by its plain value, recursively through containers."""
    if isinstance(value, SECRET_TYPES):
        return value.get_secret_value()
    if isinstance(value, dict):
        return {key: unwrap_secrets(item) for key, item in value.items()}
    if isinstance(value, list):
        return [unwrap_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(unwrap_secrets(item) for item in value)
    return value


def django_settings(settings: DjangoSettings, name: str) -> dict[str, Any]:
    """
    Return the Django settings of a settings class instance.

    These are its uppercase attributes, which is Django's own rule for what counts as a setting in a settings module,
    with secrets unwrapped, plus ``SETTINGS_CLASS`` holding the name the instance was selected by.
    """
    exported = {attr: unwrap_secrets(getattr(settings, attr)) for attr in dir(settings) if attr.isupper()}
    exported["SETTINGS_CLASS"] = name
    return exported
