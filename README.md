# IRC Book Bot

A web app that connects to irchighway's `#ebooks` IRC channel to search and download ebooks via DCC transfers. FastAPI backend, React frontend.

## Features

- **Search** - Send `@search` queries to `#ebooks`, receive and parse DCC results
- **Download** - Request books from IRC bots via DCC SEND, stored locally
- **Library** - Browse, filter, and re-download all previously fetched books
- **IP Tracking** - Every book download logs the client IP; admin can tag IPs with friendly names
- **Search Preferences** - Admin can filter formats (epub only by default) and weight/rank results by bot name, quality, etc.
- **Proxy Support** - SOCKS5 proxy rotation with auto-fetched free proxy lists, banned-IP detection
- **Stealth** - Random human-looking nicknames, random IRC client VERSION strings, fresh identity on each reconnect
- **Mobile Optimized** - Bottom tab nav, touch-friendly, responsive card layouts

## Architecture

```
backend/
  app/
    main.py          # FastAPI app, bot lifecycle, result poller
    config.py        # Env-based settings (IRCBOT_ prefix)
    auth.py          # Shared password + admin password, JWT tokens
    database.py      # Async SQLAlchemy + SQLite
    models.py        # Book, SearchSession, Download, IPTag, SearchPreferences
    irc_bot.py       # IRC client with DCC handling (background thread)
    dcc.py           # DCC SEND parser + TCP file receiver
    proxy.py         # SOCKS5 proxy manager (fetch, validate, rotate)
    nickgen.py       # Human-looking nickname + VERSION string generator
    routes/
      auth.py        # POST /api/login
      search.py      # POST /api/search, GET /api/search/{id}
      books.py       # GET /api/books, download with IP logging
      admin.py       # Download activity, IP tagging, search preferences
  storage/           # Downloaded book files
frontend/
  src/
    App.tsx          # Main app with nav (Search/Library/Admin)
    api.ts           # Typed API client
    components/      # LoginPage, SearchPage, LibraryPage, AdminPage, StatusBar
deploy/
  ircbot.service     # systemd unit file
  setup.sh           # One-time server setup
  update.sh          # Pull + rebuild + restart
data/
  ircbot.db          # SQLite database
```

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- Node.js 18+
- uv or pip

### Setup

```bash
# Clone
git clone <repo-url> ircbot && cd ircbot

# Python deps
python3 -m venv .venv
.venv/bin/pip install fastapi "uvicorn[standard]" sqlalchemy aiosqlite irc pyjwt python-multipart pydantic-settings PySocks

# Frontend
cd frontend && npm install && npm run build && cd ..

# Config
cp .env.example .env
# Edit .env to set your passwords
```

### Run

```bash
./run.sh
```

Open `http://localhost:8000`. Default password is `changeme`.

### Dev Mode (hot reload)

```bash
# Terminal 1 - backend
cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 - frontend (proxies API to backend)
cd frontend && npm run dev
```

Frontend dev server at `http://localhost:5173`.

## Deploy to Linux Server

Designed for a set-and-forget deployment on a Linux server with a Cloudflare tunnel (or any reverse proxy) in front.

### First-Time Setup

```bash
# On your server
cd /opt
sudo git clone <repo-url> ircbot
sudo bash /opt/ircbot/deploy/setup.sh
```

This will:
1. Install system deps (python3, node, npm, git)
2. Create a dedicated `ircbot` system user
3. Create a Python venv and install all dependencies
4. Build the React frontend
5. Generate a `.env` with a random JWT secret
6. Install and enable the systemd service

### Configure

```bash
sudo nano /opt/ircbot/.env
```

Set at minimum:
- `IRCBOT_PASSWORD` - shared password for regular users
- `IRCBOT_ADMIN_PASSWORD` - separate admin password

If you need proxies (e.g., your IP is banned from IRC):
- `IRCBOT_PROXY_ENABLED=true`

### Start

```bash
sudo systemctl start ircbot
```

### Point Your Tunnel

Configure your Cloudflare tunnel (or nginx/caddy) to point at:

```
http://127.0.0.1:8000
```

### Updating

```bash
sudo bash /opt/ircbot/deploy/update.sh
```

One command: pulls latest code, updates deps, rebuilds frontend, restarts the service.

### Managing the Service

| Command | What |
|---------|------|
| `sudo systemctl status ircbot` | Check if running |
| `sudo systemctl restart ircbot` | Restart |
| `sudo systemctl stop ircbot` | Stop |
| `sudo journalctl -u ircbot -f` | Follow live logs |
| `sudo journalctl -u ircbot --since "1 hour ago"` | Recent logs |
| `sudo journalctl -u ircbot -n 200` | Last 200 log lines |

## Configuration

All settings are via environment variables with the `IRCBOT_` prefix. Set them in `.env`.

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `IRCBOT_PASSWORD` | `changeme` | Shared password for regular users (search + library) |
| `IRCBOT_ADMIN_PASSWORD` | `admin` | Admin password (adds access to IP tracking, download logs, search settings) |
| `IRCBOT_JWT_SECRET` | (insecure) | Secret for signing JWT tokens. Generate a random string for production |
| `IRCBOT_JWT_EXPIRE_HOURS` | `72` | How long login tokens last |

### IRC

| Variable | Default | Description |
|----------|---------|-------------|
| `IRCBOT_IRC_SERVER` | `irc.irchighway.net` | IRC server hostname |
| `IRCBOT_IRC_PORT` | `6667` | IRC server port (6667 = plain, 6697 = SSL) |
| `IRCBOT_IRC_USE_SSL` | `false` | Use SSL/TLS for IRC connection |
| `IRCBOT_IRC_NICK` | (auto) | Leave blank to auto-generate a random human-looking nick each connection |
| `IRCBOT_IRC_CHANNEL` | `#ebooks` | Channel to join |

### Proxy

| Variable | Default | Description |
|----------|---------|-------------|
| `IRCBOT_PROXY_ENABLED` | `false` | Enable SOCKS5 proxy for IRC + DCC connections |
| `IRCBOT_PROXY_LIST_URL` | proxifly URL | URL to fetch SOCKS5 proxy list (JSON) |
| `IRCBOT_PROXY_REFRESH_MINUTES` | `30` | How often to re-fetch the proxy list |
| `IRCBOT_PROXY_MANUAL` | (empty) | Manual proxies, comma-separated `ip:port`. Overrides URL fetch |
| `IRCBOT_PROXY_CONNECT_TIMEOUT` | `10` | Seconds to wait when testing a proxy |

### Storage

| Variable | Default | Description |
|----------|---------|-------------|
| `IRCBOT_STORAGE_PATH` | `./backend/storage` | Where downloaded book files are saved |
| `IRCBOT_DB_PATH` | `./data/ircbot.db` | SQLite database path |

## How It Works

### Search Flow

1. User enters a search query in the web UI
2. Backend sends `@search <query>` to `#ebooks` on irchighway
3. A search bot sends back a results file via DCC SEND
4. Bot receives the file (may be .txt.zip compressed), parses book listings
5. Results are filtered by admin-configured format preferences (default: epub only)
6. Results are weighted/sorted by admin-configured rules (e.g., boost preferred bots)
7. Filtered results are shown in the UI

### Download Flow

1. User clicks Download on a search result
2. Backend sends the `!BotName filename` command to `#ebooks`
3. The file-serving bot sends the book via DCC SEND
4. Bot downloads the file to `storage/`, records metadata in the database
5. Book appears in the Library for anyone to download

### Proxy Flow

When `IRCBOT_PROXY_ENABLED=true`:

1. On startup, fetches ~350+ SOCKS5 proxies from proxifly's free list
2. Before connecting to IRC, iterates through proxies and health-checks each:
   - Tests SOCKS5 handshake + TCP connect to the IRC server
   - Reads initial IRC response to check for ban notices
   - Skips banned proxies, marks them with a 10-minute cooldown
3. Connects to IRC through the first clean proxy
4. DCC transfers also route through the same proxy (no IP leakage)
5. On disconnect, picks a new random proxy + new random nickname

### Stealth

- **Nicknames**: Generated from common first names, adjectives, nouns, and interests (e.g., `emma_lit23`, `quiet_owl`, `finn_txt`). Fresh nick on every connection.
- **VERSION replies**: Randomly picked from a pool of 17 real IRC client signatures (mIRC, HexChat, irssi, WeeChat, etc.)
- **No SSL fingerprint**: Uses plain TCP (port 6667) through SOCKS5 proxies to avoid SSL handshake issues and fingerprinting

## Two-Password Auth

The app uses a simple two-tier password system:

- **Regular password** (`IRCBOT_PASSWORD`): Access to Search and Library pages
- **Admin password** (`IRCBOT_ADMIN_PASSWORD`): Everything above plus Admin page with:
  - Download activity log (who downloaded what, when, from which IP)
  - IP tagging (assign friendly names like "Dave" or "Mom" to IP addresses)
  - Search settings (allowed formats, result weighting rules)

Both use the same login form. The backend encodes an `admin` claim in the JWT token.
