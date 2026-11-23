"""
WSGI config for core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()

# On Vercel, apply any pending database migrations when a new instance starts.
# This creates the tables in Neon automatically, so `migrate` never has to be
# run from a local PC. When nothing is pending it is a quick no-op.
if os.environ.get("VERCEL") and os.environ.get("AUTO_MIGRATE", "1") == "1":
    try:
        from django.core.management import call_command
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        # One quick query to see if anything is pending; skip the slow
        # migrate/createcachetable work on every cold start otherwise.
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            call_command("migrate", interactive=False, verbosity=0)
            call_command("createcachetable", verbosity=0)   # shared cache used by the login limits
    except Exception:  # never stop the site from starting because of this
        logging.getLogger(__name__).exception("Automatic migrate failed")

# Vercel looks for a variable called "app"
app = application
