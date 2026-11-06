# Module-level export instead of an import hook

django-configurations installs an import hook and ships its own `manage.py`, `wsgi.py` and `asgi.py` entry points so that `DJANGO_SETTINGS_MODULE` can point at a module that only defines classes. That hook is the part of django-configurations that aged worst: it breaks tooling that imports the settings module directly, pytest-django has to special-case it, and it is why the package blocks Python upgrades. We decided that a project's settings package instead ends with one explicit call, `setup(globals(), [...])`, which selects, validates and exports the settings class into the module. Django and every tool around it then see a plain settings module.

## Considered options

- **Import hook, as django-configurations.** Rejected: owning that importer is the maintenance burden we are escaping, and themis proved it is not needed.
- **A library-shipped settings module** (`DJANGO_SETTINGS_MODULE=pydantic_django_settings.settings` plus a dotted class path in the selector). Not rejected, only deferred: it is additive and can be built on the same `setup` later if a project wants zero glue. Its downside is that the selector would carry a dotted path instead of the short class name.
- **Frame introspection to drop the `globals()` argument.** Rejected: it saves one token and adds the one failure mode in this library that would be confusing to debug, when the call is wrapped by a helper.
