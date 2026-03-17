#!/bin/bash

# Force sync and fake initial migrations to handle the inconsistent DB state
python manage.py migrate --fake-initial --noinput

# Ensure admin account exists (uses DJANGO_ADMIN_EMAIL / DJANGO_ADMIN_PASSWORD env vars)
python manage.py ensure_admin

# Start the server with proper bindings
exec gunicorn django_finances.wsgi:application \
    --bind 0.0.0.0:${PORT:-5000} \
    --workers 3 \
    --timeout 60 \
    --forwarded-allow-ips='*'
