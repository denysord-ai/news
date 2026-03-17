#!/usr/bin/env bash
set -e

echo "Starting deploy..."

# backend
cd backend
uv sync --active --extra dev
uv run pytest

cd ../frontend
npm install

# restart service
sudo systemctl restart ai-news-backend || true
sudo systemctl restart ai-news-frontend || true

echo "Deploy done"