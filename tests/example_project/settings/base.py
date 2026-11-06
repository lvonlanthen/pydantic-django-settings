from typing import Any
from typing import ClassVar

from pydantic import Field
from pydantic import SecretStr

from pydantic_django_settings import CommaSeparatedList
from pydantic_django_settings import DjangoSettings


class Base(DjangoSettings):
    SECRET_KEY: SecretStr
    DEBUG: ClassVar[bool] = False
    ALLOWED_HOSTS: CommaSeparatedList = []
    INSTALLED_APPS: ClassVar[list[str]] = ["django.contrib.contenttypes"]

    database_password: SecretStr = Field(SecretStr(""), validation_alias="DATABASE_PASSWORD")

    @property
    def DATABASES(self) -> dict[str, Any]:
        return {"default": {"ENGINE": "django.db.backends.sqlite3", "PASSWORD": self.database_password}}
