#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deploy the Radio Show Editor backend to a cloud server
# =============================================================================
# This script automates first-time setup on a fresh Linux server (Ubuntu/Debian).
#
# Usage:
#   1. SSH into your server
#   2. Clone the repository
#   3. Copy .env.example to .env and fill in your secrets
#   4. Run: bash deploy.sh
#
# Prerequisites:
#   - A server with at least 4 GB RAM (8 GB recommended for ML models)
#   - Ubuntu 20.04+ or Debian 11+
#   - Root or sudo access
# =============================================================================

set -euo pipefail

# ── Colours for output ─────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ── Check .env file exists ────────────────────────────────────────────────
if [ ! -f .env ]; then
    error ".env file not found."
    echo "  Copy the example and fill in your secrets:"
    echo "    cp .env.example .env"
    echo "    nano .env"
    exit 1
fi

# ── Install Docker if not present ─────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker "$USER"
    info "Docker installed. You may need to log out and back in for group changes."
fi

# ── Install Docker Compose plugin if not present ──────────────────────────
if ! docker compose version &> /dev/null; then
    info "Installing Docker Compose plugin..."
    sudo apt-get update && sudo apt-get install -y docker-compose-plugin
fi

# ── Build and start services ─────────────────────────────────────────────
info "Building and starting services..."
docker compose up --build -d

# ── Wait for health check ────────────────────────────────────────────────
info "Waiting for the API to become healthy..."
RETRIES=30
until docker compose exec web curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    RETRIES=$((RETRIES - 1))
    if [ "$RETRIES" -le 0 ]; then
        warn "Health check did not pass within timeout. Check logs:"
        echo "  docker compose logs web"
        exit 1
    fi
    sleep 2
done

info "All services are running!"
echo ""
echo "  API endpoint:    http://$(hostname -I | awk '{print $1}'):${API_PORT:-8000}"
echo "  Health check:    http://$(hostname -I | awk '{print $1}'):${API_PORT:-8000}/health"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f          Follow all logs"
echo "    docker compose logs -f worker   Follow Celery worker logs"
echo "    docker compose ps               Show running services"
echo "    docker compose down             Stop all services"
echo "    docker compose up -d --build    Rebuild and restart"
