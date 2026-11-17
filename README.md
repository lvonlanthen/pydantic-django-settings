# pydantic-django-settings

Define Django settings as [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) classes, one per environment, and select one with `DJANGO_SETTINGS_CLASS`. A successor to [django-configurations](https://github.com/jazzband/django-configurations) for projects that want their settings validated at startup, their secrets kept out of error messages, and no import hook.

```python
# myproject/settings/__init__.py
from pydantic_django_settings import setup

from myproject.settings.environments import Development, Production, Testing

setup(globals(), [Development, Production, Testing], default="Development")
```

```
DJANGO_SETTINGS_MODULE=myproject.settings DJANGO_SETTINGS_CLASS=Production python manage.py check
```

Django keeps using the plain `DJANGO_SETTINGS_MODULE`. The one `setup` call at the end of the settings package selects the class named by `DJANGO_SETTINGS_CLASS`, instantiates it from the environment, and exports its uppercase attributes as module globals, which is all Django expects from a settings module. No custom `manage.py`, `wsgi.py` or `asgi.py`.

## Installation

```
pip install pydantic-django-settings
```

Requires Python 3.12+, Django 5.2+ and pydantic-settings 2.7+.

## Writing settings classes

Every settings class inherits from `DjangoSettings`, a `pydantic_settings.BaseSettings` with these conventions:

- fields are read from the environment as `DJANGO_<FIELD>`, or from the exact variable named by `validation_alias`;
- variable names are case sensitive;
- an empty variable counts as unset, so `DJANGO_DEBUG_TOOLBAR=` falls back to the default;
- values are validated against the field type, so `DJANGO_SESSION_COOKIE_AGE=soon` aborts the startup instead of being ignored.

Every uppercase attribute is a Django setting. There are three kinds:

```python
from pathlib import Path
from typing import Any, ClassVar

from pydantic import Field, SecretStr
from pydantic_django_settings import CommaSeparatedList, DjangoSettings


class Base(DjangoSettings):
    # Fixed: a ClassVar is the same for every deployment and ignores the environment.
    # Use this for everything that is not meant to be tuned per deployment, in particular
    # DEBUG, the SECURE_* and cookie flags, INSTALLED_APPS and MIDDLEWARE.
    BASE_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent
    DEBUG: ClassVar[bool] = False
    INSTALLED_APPS: ClassVar[list[str]] = ["django.contrib.admin", "django.contrib.auth"]

    # Environment: a pydantic field is read from DJANGO_<FIELD> and validated.
    SECRET_KEY: SecretStr
    ALLOWED_HOSTS: CommaSeparatedList = []
    SESSION_COOKIE_AGE: int = 12 * 60 * 60

    # A validation_alias names the exact variable, without the prefix.
    SENTRY_DSN: str | None = Field(None, validation_alias="SENTRY_DSN")

    # Lowercase fields are inputs for computed settings and are not exported.
    database_name: str = Field("myproject", validation_alias="DJANGO_DATABASE_NAME")
    database_password: SecretStr = Field(SecretStr(""), validation_alias="DJANGO_DATABASE_PASSWORD")

    # Computed: a property derives a setting from other attributes.
    @property
    def DATABASES(self) -> dict[str, Any]:
        return {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": self.database_name,
                "PASSWORD": self.database_password,
            }
        }


class Development(Base):
    DEBUG: ClassVar[bool] = True
    SECRET_KEY: SecretStr = SecretStr("development")
    ALLOWED_HOSTS: CommaSeparatedList = ["*"]


class Production(Base):
    ALLOWED_HOSTS: CommaSeparatedList = Field(min_length=1)
    SESSION_COOKIE_SECURE: ClassVar[bool] = True
    SECURE_SSL_REDIRECT: ClassVar[bool] = True
    database_password: SecretStr = Field(validation_alias="DJANGO_DATABASE_PASSWORD")


class Testing(Base):
    SECRET_KEY: SecretStr = SecretStr("testing")
    PASSWORD_HASHERS: ClassVar[list[str]] = ["django.contrib.auth.hashers.MD5PasswordHasher"]
```

Mixins are settings classes too: `class Production(LoggingSettings, SentrySettings, Base)` composes them like any pydantic model.

Two things to know when overriding a field in a subclass:

- An override replaces the whole field definition, so repeat the `validation_alias` and the `CommaSeparatedList` annotation, otherwise the variable name or the list format silently changes.
- Omitting the default, as `Production` does for `database_password`, makes the variable required, which is how production fails fast at startup instead of at the first query.

### Secrets

Declare secrets as `SecretStr`, `SecretBytes` or `Secret[T]`. Inside the pydantic layer they are masked in reprs and validation errors. On export they are unwrapped to plain values, recursively through dicts, lists and tuples, so a computed `DATABASES` can pass `self.database_password` through untouched and Django still receives a string.

### `CommaSeparatedList`

pydantic-settings parses list fields from the environment as JSON. `CommaSeparatedList` reads `DJANGO_ALLOWED_HOSTS=a.example.ch, b.example.ch` instead, stripping whitespace and dropping empty items, which is what django-configurations' `ListValue` did.

It is `list[str]` only. For another item type, a tuple or a set, annotate the field with the same splitter, `split_comma_separated`, and let pydantic convert the items:

```python
from typing import Annotated

from pydantic import BeforeValidator
from pydantic_django_settings import split_comma_separated
from pydantic_settings import NoDecode

PORTS: Annotated[list[int], NoDecode, BeforeValidator(split_comma_separated)] = []
LANGUAGES: Annotated[tuple[str, ...], NoDecode, BeforeValidator(split_comma_separated)] = ()
```

### URL-based settings

This library does not parse URLs such as `DATABASE_URL`. Use the packages that django-configurations wrapped in its `DatabaseURLValue`, `CacheURLValue`, `EmailURLValue` and `SearchURLValue`: [dj-database-url](https://pypi.org/project/dj-database-url/), [django-cache-url](https://pypi.org/project/django-cache-url/), [dj-email-url](https://pypi.org/project/dj-email-url/) and [dj-search-url](https://pypi.org/project/dj-search-url/). Read the URL into a lowercase field and compute the setting from it:

```python
import dj_database_url


class Base(DjangoSettings):
    database_url: SecretStr = Field(validation_alias="DATABASE_URL")

    @property
    def DATABASES(self) -> dict[str, Any]:
        return {"default": dj_database_url.parse(self.database_url.get_secret_value())}
```

Call the package's `parse()` on the field instead of its `config()`, which reads `os.environ` itself and so bypasses the validation: with the field, a missing variable is reported as `DATABASE_URL: Field required` like any other. Declare the URL as `SecretStr`, since it carries the password. A URL that is set but malformed raises the parser's own exception, e.g. `dj_database_url.UnknownSchemeError`, not `ImproperlyConfigured`.

A parser that returns several settings, as dj-email-url does, needs one property per setting, because only uppercase attributes are exported:

```python
import dj_email_url


class EmailSettings(DjangoSettings):
    email_url: SecretStr = Field(SecretStr("console://"), validation_alias="EMAIL_URL")

    @property
    def _email(self) -> dict[str, Any]:
        return dj_email_url.parse(self.email_url.get_secret_value())

    @property
    def EMAIL_BACKEND(self) -> str:
        return self._email["EMAIL_BACKEND"]

    @property
    def EMAIL_HOST(self) -> str:
        return self._email["EMAIL_HOST"]

    # ... and so on for EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_USE_TLS
```

### `post_setup`

`DjangoSettings.post_setup()` is a no-op hook that `setup` runs after the export, for things like initialising an error-reporting SDK:

```python
class SentrySettings(DjangoSettings):
    SENTRY_DSN: str | None = Field(None, validation_alias="SENTRY_DSN")

    def post_setup(self) -> None:
        super().post_setup()
        if self.SENTRY_DSN:
            import sentry_sdk

            sentry_sdk.init(dsn=self.SENTRY_DSN)
```

## Selecting the settings class

`setup(namespace, classes, *, default=None)` resolves `DJANGO_SETTINGS_CLASS` against the explicit list of classes. Only listed classes are selectable, so a mixin or a base class never is. The value is the class name, e.g. `Production`. An empty variable counts as unset; unset falls back to `default`, and without a default `setup` raises `ImproperlyConfigured` listing the valid names. The call returns the instance, in case you want a typed reference next to the module globals.

Set the default per entry point with `os.environ.setdefault`, as Django's own templates do for `DJANGO_SETTINGS_MODULE`: `Development` in `manage.py`, `Production` in `wsgi.py` and `asgi.py`. The `default` argument of `setup` covers tools that import the settings module directly, such as the mypy django-stubs plugin.

The selected name is exported as the Django setting `SETTINGS_CLASS`, so code can ask which environment it runs in:

```python
if settings.SETTINGS_CLASS == "TestingE2E":
    urlpatterns += e2e_urlpatterns
```

## Errors

A settings class that fails validation raises `django.core.exceptions.ImproperlyConfigured` naming the environment variables and the problems, for example:

```
Invalid settings for Production: DJANGO_SECRET_KEY: Field required; DJANGO_ALLOWED_HOSTS: Field required; DJANGO_SESSION_COOKIE_AGE: Input should be a valid integer, unable to parse string as an integer
```

The pydantic `ValidationError` is deliberately not chained, because its message echoes the input values, including secrets, into the log.

This holds for pydantic's own types, whose messages name the expected values and constraints only. A custom `field_validator` that puts the value into its own message defeats it, so keep values out of validator messages. Malformed JSON for a list, dict or model field that is not a `CommaSeparatedList` is reported the same way, as `DJANGO_PORTS: value is not valid JSON`.

## pytest

The package registers a pytest plugin that sets `DJANGO_SETTINGS_CLASS` before pytest-django loads the settings, with the same precedence pytest-django applies to `DJANGO_SETTINGS_MODULE`: the `--django-settings-class` option, then the environment, then the ini option.

```toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "myproject.settings"
DJANGO_SETTINGS_CLASS = "Testing"
```

The pytest header reports what was picked: `settings class: Testing (from ini)`. Note that, as for `DJANGO_SETTINGS_MODULE`, a variable exported in the shell or container beats the ini value.

## Migrating from django-configurations

1. Replace the dependency `django-configurations` with `pydantic-django-settings`.
2. Rename `DJANGO_CONFIGURATION` to `DJANGO_SETTINGS_CLASS` everywhere: `manage.py`, `wsgi.py`, `asgi.py`, Dockerfiles, compose files, CI, deployment templates and the pytest ini. The old name cannot stay: pytest-django hard-wires it to the django-configurations importer.
3. In `manage.py`, `wsgi.py` and `asgi.py`, import `execute_from_command_line`, `get_wsgi_application` and `get_asgi_application` from Django again instead of from `configurations`.
4. Change the base class from `configurations.Configuration` to `DjangoSettings`, and mixins from plain classes to `DjangoSettings` subclasses.
5. Add a type annotation to every attribute, and decide its kind: `values.Value(...)` becomes a pydantic field with the matching type, with `validation_alias` where `environ_name` or `environ_prefix` was used; everything else becomes a `ClassVar`. django-configurations only read the environment for explicit `values.Value` attributes, so the same set of settings stays tunable. Wrap secrets in `SecretStr`. `DatabaseURLValue` and the other URL values become a field plus a computed setting, see [URL-based settings](#url-based-settings).
6. Turn `post_setup` classmethods into instance methods: `cls` becomes `self`.
7. Replace `settings.CONFIGURATION`, which held a dotted path, with `settings.SETTINGS_CLASS`, which holds the class name.
8. End the settings package with `setup(globals(), [...], default="Development")` and remove any `DJANGO_CONFIGURATION` fallback.

How each `values` class translates. A `validation_alias` is the full variable name, so `environ_name="FOO"`, which django-configurations read from `DJANGO_FOO`, becomes `validation_alias="DJANGO_FOO"`.

| django-configurations | Environment format | Here |
|---|---|---|
| `Value` | string | `str` |
| `Value(environ=False)` | not read | `ClassVar` |
| `environ_required=True` | must be set | a field without a default |
| `BooleanValue` | `yes`, `no`, `true`, `false`, `1`, `0`, … | `bool` |
| `IntegerValue`, `FloatValue`, `DecimalValue` | number | `int`, `float`, `Decimal` |
| `PositiveIntegerValue` | number, zero allowed | `NonNegativeInt` |
| `ListValue` | `a,b,c` | `CommaSeparatedList` |
| `ListValue(converter=int)`, `TupleValue`, `SetValue` | `a,b,c` | `split_comma_separated` with `list[int]`, `tuple[str, ...]`, `set[str]`, see [`CommaSeparatedList`](#commaseparatedlist) |
| `separator=` other than a comma | `a;b;c` | your own `BeforeValidator`, or JSON |
| `SingleNestedListValue`, `SingleNestedTupleValue` | `a,b;c,d` | `list[list[str]]`, given as JSON `[["a","b"],["c","d"]]` |
| `DictValue` | Python literal `{'a': 1}` | `dict[str, Any]`, given as JSON `{"a": 1}` |
| `BackendsValue` | `a.B,c.D` | `CommaSeparatedList`, without the check that each path imports |
| `EmailValue` | string | `EmailStr`, which needs `pydantic[email]` |
| `URLValue` | string | `AnyUrl` or `HttpUrl`; the setting is then a URL object, not a `str` |
| `IPValue` | string | `IPvAnyAddress`; the setting is then an `ipaddress` object, not a `str` |
| `RegexValue(regex=...)` | string | `str` with `Field(pattern=...)` |
| `PathValue` | path that must exist | `FilePath` or `DirectoryPath`; `Path` for `check_exists=False`. `~` is not expanded |
| `SecretValue` | must be set and non-empty | `SecretStr` without a default |
| `DatabaseURLValue`, `CacheURLValue`, `EmailURLValue`, `SearchURLValue` | URL | [URL-based settings](#url-based-settings) |

Behaviour that changes:

- Nested sequences and dicts are given as JSON, so a deployment that sets a `SingleNestedListValue` or a `DictValue` through the environment has to reformat that value.

- django-configurations copied every Django default onto the class, which made Django warn about deprecated settings you never set. This library exports only what you declare.
- Booleans: an empty variable counts as unset instead of false, and pydantic accepts `on`/`off`/`t`/`f` in addition to `true`/`false`/`yes`/`no`/`1`/`0`.
- A missing or malformed value aborts the startup instead of being ignored.

If you use ruff with `RUF012` enabled, it flags mutable field defaults such as `ALLOWED_HOSTS: CommaSeparatedList = []` on your subclasses, because ruff only recognises classes that inherit from pydantic directly. Pydantic copies field defaults per instance, so the rule does not apply; ignore it for your settings package.

## License

MIT
