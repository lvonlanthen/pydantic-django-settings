from pathlib import Path
from typing import Any
from typing import ClassVar

from pydantic import Secret
from pydantic import SecretBytes
from pydantic import SecretStr

from pydantic_django_settings.base import DjangoSettings
from pydantic_django_settings.export import django_settings
from pydantic_django_settings.export import unwrap_secrets


class Settings(DjangoSettings):
    DEBUG: ClassVar[bool] = True
    BASE_DIR: ClassVar[Path] = Path("/srv/app")
    SECRET_KEY: SecretStr = SecretStr("s3cret")
    API_TOKEN: SecretBytes = SecretBytes(b"token")
    PIN: Secret[int] = Secret(1234)
    DISABLE_2FA: bool = False
    database_name: str = "db"
    database_password: SecretStr = SecretStr("db-secret")

    @property
    def DATABASES(self) -> dict[str, Any]:
        return {"default": {"NAME": self.database_name, "PASSWORD": self.database_password}}

    @property
    def CREDENTIALS(self) -> tuple[Any, ...]:
        return (self.database_name, self.database_password, [self.SECRET_KEY])


def test_exports_uppercase_attributes_of_all_three_kinds() -> None:
    exported = django_settings(Settings(), "Settings")
    assert exported["DEBUG"] is True
    assert exported["BASE_DIR"] == Path("/srv/app")
    assert exported["DISABLE_2FA"] is False
    assert exported["DATABASES"]["default"]["NAME"] == "db"
    assert "database_name" not in exported
    assert "database_password" not in exported
    assert "model_config" not in exported
    assert "post_setup" not in exported
    assert all(name.isupper() for name in exported)


def test_exports_the_settings_class_name() -> None:
    assert django_settings(Settings(), "Testing")["SETTINGS_CLASS"] == "Testing"


def test_unwraps_top_level_secrets() -> None:
    exported = django_settings(Settings(), "Settings")
    assert exported["SECRET_KEY"] == "s3cret"
    assert exported["API_TOKEN"] == b"token"
    assert exported["PIN"] == 1234


def test_unwraps_secrets_nested_in_containers() -> None:
    exported = django_settings(Settings(), "Settings")
    assert exported["DATABASES"] == {"default": {"NAME": "db", "PASSWORD": "db-secret"}}
    assert exported["CREDENTIALS"] == ("db", "db-secret", ["s3cret"])


def test_unwrap_secrets_leaves_other_values_untouched() -> None:
    value = {"path": Path("/x"), "nested": {"items": [1, "two", None]}, "flag": True}
    assert unwrap_secrets(value) == value
    assert unwrap_secrets(Path("/x")) == Path("/x")
