#!/usr/bin/env bash
set -euo pipefail

# Apply DB migrations on each boot (safe to re-run, skips already-applied).
python manage.py migrate --noinput

# Replit exposes the service port via $PORT.
exec gunicorn django_finances.wsgi:application \
  --bind 0.0.0.0:${PORT:-5000} \
  --workers 3 \
  --timeout 60 \
  --forwarded-allow-ips='*'
