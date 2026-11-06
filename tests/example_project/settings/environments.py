from typing import ClassVar

from pydantic import Field
from pydantic import SecretStr

from example_project.settings.base import Base
from pydantic_django_settings import CommaSeparatedList


class Development(Base):
    DEBUG: ClassVar[bool] = True
    SECRET_KEY: SecretStr = SecretStr("dev")
    ALLOWED_HOSTS: CommaSeparatedList = ["*"]


class Production(Base):
    ALLOWED_HOSTS: CommaSeparatedList = Field(min_length=1)


class Testing(Base):
    SECRET_KEY: SecretStr = SecretStr("testing")
