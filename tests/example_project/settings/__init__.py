from example_project.settings.environments import Development
from example_project.settings.environments import Production
from example_project.settings.environments import Testing
from pydantic_django_settings import setup


setup(globals(), [Development, Production, Testing], default="Development")
