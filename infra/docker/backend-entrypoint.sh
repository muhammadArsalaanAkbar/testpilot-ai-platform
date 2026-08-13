#!/bin/sh
# Runs migrations before handing off to whichever process this container's
# CMD (or docker-compose `command:` override) actually starts — the api
# and worker services share this one entrypoint (quickstart.md Section 2:
# "Alembic migrations apply automatically on api/worker container start in
# the dev compose file"). `alembic upgrade head` is a no-op if already
# current, so both containers running it at startup is safe.
set -e

alembic upgrade head

exec "$@"
