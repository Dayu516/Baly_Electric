#!/bin/bash
# 部署腳本 — 在 VPS 上執行
# Usage: bash scripts/deploy.sh

set -e

echo "=== OTTIMO Deploy ==="

# 1. Pull latest code
git pull origin main

# 2. Build and restart
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 3. Run migrations
docker compose -f docker-compose.prod.yml exec app alembic upgrade head

# 4. Health check
sleep 5
curl -f http://localhost:8000/health && echo " => OK" || echo " => FAILED"

echo "=== Deploy complete ==="
