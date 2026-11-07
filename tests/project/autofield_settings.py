"""The test project as a project left on Django's default primary key."""

from tests.project.settings import *  # noqa: F403

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'
