#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies using uv
# We assume 'uv' is available in the environment or installed via a previous step
# If Render doesn't have 'uv' pre-installed, you might need to install it:
# curl -LsSf https://astral.sh/uv/install.sh | sh
# source $HOME/.cargo/env

uv sync --frozen
uv cache prune --ci

# Collect static files
uv run python manage.py collectstatic --no-input

# Run migrations
uv run python manage.py migrate

# Reset axes lockout records (clear any accumulated failed login attempts)
uv run python manage.py axes_reset
