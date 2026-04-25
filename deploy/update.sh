#!/usr/bin/env bash
# Pull latest code, rebuild, and restart the service.
# Run as root: sudo bash deploy/update.sh
set -euo pipefail

APP_DIR="/opt/ircbot"

echo "=== IRC Book Bot - Update ==="

cd "$APP_DIR"

# Pull latest
echo "[1/4] Pulling latest code..."
sudo -u ircbot git pull

# Update Python deps
echo "[2/4] Updating Python deps..."
"$APP_DIR/.venv/bin/pip" install -q \
    fastapi "uvicorn[standard]" sqlalchemy aiosqlite irc pyjwt python-multipart pydantic-settings PySocks

# Rebuild frontend
echo "[3/4] Rebuilding frontend..."
cd "$APP_DIR/frontend"
npm install --silent
npm run build --silent
cd "$APP_DIR"

# Fix ownership and restart
chown -R ircbot:ircbot "$APP_DIR"

echo "[4/4] Restarting service..."
systemctl restart ircbot

echo ""
echo "=== Update complete ==="
systemctl status ircbot --no-pager
