# pydantic-django-settings

A library that lets a Django project define its settings as pydantic-settings classes, one per environment, and hands the selected class to Django as a plain settings module. It replaces django-configurations.

## Language

**Settings class**:
A pydantic-settings model whose uppercase attributes are the Django settings of one environment, such as Development, Production or Testing.
_Avoid_: Configuration, settings model, environment class

**Selector**:
The environment variable `DJANGO_SETTINGS_CLASS` that names which settings class to load.
_Avoid_: Configuration variable, DJANGO_CONFIGURATION

**Setup**:
Selecting a settings class by the selector, instantiating it from the environment, exporting it and running its post-setup hook.
_Avoid_: Configure, install, bootstrap

**Export**:
Copying the uppercase attributes of a settings class instance into the Django settings module, with secrets unwrapped to plain values.
_Avoid_: Configure, install

**Fixed setting**:
A setting declared as a ClassVar, so it is the same for every deployment of a settings class and ignores the environment.
_Avoid_: Constant, static setting

**Environment setting**:
A setting declared as a pydantic field, so it is read from the environment and validated at setup.
_Avoid_: Value, env setting, variable

**Computed setting**:
A setting declared as a property, derived from other attributes of the settings class.
_Avoid_: Derived setting, dynamic setting
