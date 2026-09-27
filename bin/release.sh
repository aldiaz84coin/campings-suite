#!/bin/sh
# Runs once per deploy on Fly.io (see [deploy] in fly.toml), before the new
# version starts serving traffic.
set -e
python manage.py migrate --noinput
python manage.py ensure_superuser
