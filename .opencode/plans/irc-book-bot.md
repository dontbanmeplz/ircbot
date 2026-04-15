# IRC Book Download Bot - Implementation Plan

## Overview
Web app with **FastAPI backend** + **React frontend** connecting to irchighway's `#ebooks` channel. Lets authenticated users search for and download books via IRC DCC transfers. Stores books locally, tracks download activity by IP with manual tagging.

## Tech Stack
- **Backend**: FastAPI (Python 3.13), `jaraco/irc` for IRC, SQLite via SQLAlchemy, uv for packages
- **Frontend**: React (Vite + TypeScript)
- **IRC**: `jaraco/irc` with manual DCC SEND handling, running in a background thread
- **Auth**: Single shared password, JWT tokens

## User Decisions
- IRC: Auto @search in #ebooks
- Auth: Single shared password (everything behind password)
- IP Tracking: Log IP per download + manual tagging
- Package manager: uv
- IRC library: jaraco/irc + manual DCC

## Project Structure

```
ircbot/
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py              # FastAPI app, startup/shutdown
│   │   ├── config.py            # Settings (password, IRC server, paths)
│   │   ├── auth.py              # Simple shared-password auth (JWT)
│   │   ├── database.py          # SQLAlchemy async setup, SQLite
│   │   ├── models.py            # DB models (Book, SearchSession, Download, IPTag)
│   │   ├── irc_bot.py           # IRC client - connect, search, DCC receive
│   │   ├── dcc.py               # DCC SEND parser + raw TCP file receiver
│   │   └── routes/
│   │       ├── auth.py          # POST /api/login
│   │       ├── books.py         # GET /api/books, GET /api/books/{id}/download
│   │       ├── search.py        # POST /api/search, GET /api/search/{id}
│   │       └── admin.py         # GET /api/downloads, POST /api/ip-tags
│   └── storage/                 # Downloaded book files (gitignored)
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api.ts               # API client
│   │   ├── components/
│   │   │   ├── LoginPage.tsx
│   │   │   ├── SearchPage.tsx
│   │   │   ├── LibraryPage.tsx
│   │   │   └── AdminPage.tsx    # IP tracking + tagging
│   │   └── ...
└── data/
    └── ircbot.db                # SQLite database (gitignored)
```

## Database Models

### Books
- id (int PK), title, author, filename, file_path, file_size, format (epub/pdf/mobi), source_bot, created_at

### SearchSessions
- id (int PK), query, status (pending/complete/failed), results_json (JSON text), created_at

### Downloads (IP tracking)
- id (int PK), book_id (FK), ip_address, user_agent, downloaded_at

### IPTags (manual tagging)
- id (int PK), ip_address (unique), tag_name (e.g. "Dave"), notes, created_at, updated_at

## IRC Bot Technical Details

### Connection
- Server: `irc.irchighway.net:6697` (TLS)
- Join `#ebooks` after 2s delay post-connect
- Handle PING/PONG and VERSION CTCP responses
- Use `jaraco/irc` SimpleIRCClient with select-based reactor in background thread

### Search Flow
1. Send `@search <query>` as PRIVMSG to #ebooks
2. Search bot sends NOTICE with acknowledgment
3. Search bot initiates DCC SEND with results file
4. Parse CTCP: `DCC SEND "?(.+[^"])"?\s(\d+)\s+(\d+)\s+(\d+)\s*`
5. Convert integer IP to dotted quad
6. Open raw TCP socket, read exactly filesize bytes (NO EOF from server!)
7. Results file may be .txt.zip -> decompress if needed
8. Parse results: lines starting with `!` are book entries
   Format: `!<botname> Author - Title.format ::INFO:: size`

### Download Flow
1. Send full `!BotName Author - Title.epub` as PRIVMSG to #ebooks
2. File bot initiates DCC SEND
3. Same DCC receive process as search results
4. Save file to storage/, record metadata in DB

### Critical DCC Quirks
- **No EOF**: DCC server does NOT close connection. Must track bytes received vs declared filesize.
- **Integer IP**: Sent as big-endian 32-bit unsigned int in decimal string
- **Filename quoting**: May or may not be wrapped in double quotes
- **Compressed results**: Search results can be .txt.zip
- **VERSION CTCP**: Must respond or risk kick
- **Read performance**: Manual chunked reads recommended over buffered copy

### Thread Communication
- FastAPI <-> IRC bot via thread-safe queues
- Search request queue: FastAPI pushes search queries
- Search result queue: Bot pushes parsed results back
- Download request queue: FastAPI pushes download commands
- Download complete queue: Bot pushes completed download info

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/login` | No | Auth with shared password, returns JWT |
| POST | `/api/search` | Yes | Start a book search, returns session ID |
| GET | `/api/search/{id}` | Yes | Poll search status + results |
| POST | `/api/download` | Yes | Request a book download from IRC |
| GET | `/api/books` | Yes | List all downloaded books |
| GET | `/api/books/{id}` | Yes | Get book details |
| GET | `/api/books/{id}/download` | Yes | Download book file (logs IP) |
| GET | `/api/admin/downloads` | Yes | View all download activity with IP tags |
| GET | `/api/admin/ip-tags` | Yes | List all tagged IPs |
| POST | `/api/admin/ip-tags` | Yes | Tag an IP address |
| PUT | `/api/admin/ip-tags/{id}` | Yes | Update a tag |
| DELETE | `/api/admin/ip-tags/{id}` | Yes | Remove a tag |
| GET | `/api/status` | Yes | IRC bot connection status |

## Frontend Pages

### Login Page
- Password input field + submit button
- Stores JWT in localStorage
- Redirects to search page on success

### Search Page (main page)
- Search bar at top
- Loading state while search runs
- Results list with: title, author, format, size, download button
- Active downloads shown with progress indicator

### Library Page
- Grid/list of all downloaded books
- Search/filter by title, author, format
- Download button on each book
- Shows file size, download date

### Admin Page
- **Download Log Table**: timestamp, book title, IP address, tagged name (if any), user agent
- **IP Tags Section**: list of tagged IPs with name/notes, edit/delete buttons
- **Tag Form**: click an IP to tag it, enter friendly name + optional notes
- Filterable by IP, tag name, date range

## Implementation Order

1. Backend project setup (pyproject.toml, uv install)
2. Database models + setup
3. Config + auth system
4. IRC bot + DCC file handling
5. API routes
6. FastAPI main app with bot lifecycle
7. React frontend scaffold (Vite)
8. Frontend pages
9. Integration testing

## Dependencies

### Backend (pyproject.toml)
```
fastapi>=0.115
uvicorn[standard]>=0.34
sqlalchemy>=2.0
aiosqlite>=0.20
irc>=20.5
pyjwt>=2.9
python-multipart>=0.0.18
pydantic-settings>=2.7
```

### Frontend
```
react, react-dom, react-router-dom
typescript, vite
```

## Environment Variables
```
IRCBOT_PASSWORD=<shared access password>
IRCBOT_JWT_SECRET=<random secret for JWT signing>
IRCBOT_IRC_SERVER=irc.irchighway.net
IRCBOT_IRC_PORT=6697
IRCBOT_IRC_NICK=<bot nickname>
IRCBOT_STORAGE_PATH=./storage
IRCBOT_DB_PATH=./data/ircbot.db
```
