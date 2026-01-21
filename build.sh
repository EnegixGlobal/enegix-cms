#!/usr/bin/env bash
# Build script for Render deployment

# Install dependencies (Render does this automatically, but we can run migrations and collect static)
python manage.py migrate --noinput
python manage.py collectstatic --noinput

