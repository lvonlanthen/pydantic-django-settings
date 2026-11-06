# pydantic-django-settings

Define Django settings as [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) classes, one per environment, and select one with `DJANGO_SETTINGS_CLASS`. A drop-in successor to [django-configurations](https://github.com/jazzband/django-configurations) for projects that want their settings validated at startup, their secrets kept out of error messages, and no import hook.

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
5. Add a type annotation to every attribute, and decide its kind: `values.Value(...)` becomes a pydantic field with the matching type, with `validation_alias` where `environ_name` or `environ_prefix` was used; everything else becomes a `ClassVar`. django-configurations only read the environment for explicit `values.Value` attributes, so the same set of settings stays tunable. Wrap secrets in `SecretStr`.
6. Turn `post_setup` classmethods into instance methods: `cls` becomes `self`.
7. Replace `settings.CONFIGURATION`, which held a dotted path, with `settings.SETTINGS_CLASS`, which holds the class name.
8. End the settings package with `setup(globals(), [...], default="Development")` and remove any `DJANGO_CONFIGURATION` fallback.

Behaviour that changes:

- django-configurations copied every Django default onto the class, which made Django warn about deprecated settings you never set. This library exports only what you declare.
- Booleans: an empty variable counts as unset instead of false, and pydantic accepts `on`/`off`/`t`/`f` in addition to `true`/`false`/`yes`/`no`/`1`/`0`.
- A missing or malformed value aborts the startup instead of being ignored.

If you use ruff with `RUF012` enabled, it flags mutable field defaults such as `ALLOWED_HOSTS: CommaSeparatedList = []` on your subclasses, because ruff only recognises classes that inherit from pydantic directly. Pydantic copies field defaults per instance, so the rule does not apply; ignore it for your settings package.

## License

MIT
