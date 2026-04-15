#!/usr/bin/env bash
# One-time server setup for IRC Book Bot
# Run as root: sudo bash deploy/setup.sh
set -euo pipefail

APP_DIR="/opt/ircbot"
APP_USER="ircbot"

echo "=== IRC Book Bot - Server Setup ==="

# 1. Install system deps
echo "[1/7] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nodejs npm git > /dev/null

# 2. Create service user
echo "[2/7] Creating service user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir "$APP_DIR" "$APP_USER"
fi

# 3. Clone or copy the project
echo "[3/7] Setting up app directory..."
if [ ! -d "$APP_DIR" ]; then
    # If running from the repo, copy it
    if [ -f "$(dirname "$0")/../backend/app/main.py" ]; then
        cp -r "$(dirname "$0")/.." "$APP_DIR"
    else
        echo "ERROR: Run this from the project root, or clone the repo to $APP_DIR first."
        exit 1
    fi
fi

# 4. Python venv + deps
echo "[4/7] Setting up Python venv..."
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q \
    fastapi "uvicorn[standard]" sqlalchemy aiosqlite irc pyjwt python-multipart pydantic-settings

# 5. Build frontend
echo "[5/7] Building frontend..."
cd "$APP_DIR/frontend"
npm install --silent
npm run build --silent
cd "$APP_DIR"

# 6. Create .env if missing
echo "[6/7] Checking .env..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    # Generate a random JWT secret
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    sed -i "s/change-this-to-a-random-secret/$JWT_SECRET/" "$APP_DIR/.env"
    echo "  Created .env - EDIT IT NOW to set your passwords:"
    echo "  sudo nano $APP_DIR/.env"
fi

# Create data + storage dirs
mkdir -p "$APP_DIR/data" "$APP_DIR/backend/storage"

# Fix ownership
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# 7. Install and enable systemd service
echo "[7/7] Installing systemd service..."
cp "$APP_DIR/deploy/ircbot.service" /etc/systemd/system/ircbot.service
systemctl daemon-reload
systemctl enable ircbot

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit your config:    sudo nano $APP_DIR/.env"
echo "  2. Start the service:   sudo systemctl start ircbot"
echo "  3. Check status:        sudo systemctl status ircbot"
echo "  4. View logs:           sudo journalctl -u ircbot -f"
echo ""
echo "Point your Cloudflare tunnel to:  http://127.0.0.1:8000"
