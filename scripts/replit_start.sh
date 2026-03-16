#!/usr/bin/env bash
set -euo pipefail

# Apply DB migrations. --fake-initial skips creating tables that already exist
# in the DB but are missing from Django's migration history (fixes DuplicateTable errors).
python manage.py migrate --noinput --fake-initial

# Replit exposes the service port via $PORT.
exec gunicorn django_finances.wsgi:application \
  --bind 0.0.0.0:${PORT:-5000} \
  --workers 3 \
  --timeout 60 \
  --forwarded-allow-ips='*'
