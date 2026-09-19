#!/bin/sh
# Boot-seed: fresh, known-good demo state on every start (ephemeral disk), then serve.
set -e

echo "Seeding demo data and processing the inbox..."
python -m scripts.demo --no-serve || true

echo "Starting web app on :8000"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
