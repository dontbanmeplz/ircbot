# IRC Book Downloader Web Interface

A web-based interface for searching and downloading ebooks from IRC channels using DCC transfers. Built with Flask, Socket.IO, and the existing `AsyncDCCBot` IRC client.

## Features

- **Password-Protected Access** - Simple authentication to secure your downloads
- **On-Demand IRC Connection** - Connects only when needed, disconnects after 5 minutes of inactivity
- **Multi-User Queue System** - Handles multiple search/download requests in FIFO order
- **Real-Time Updates** - WebSocket-powered live progress tracking
- **Search & Browse** - Search for books and view results grouped by bot source
- **Persistent Library** - All downloaded books are saved with metadata for easy browsing
- **Advanced Filtering** - Search library by title, author, format, or source
- **Automatic Duplicate Handling** - Replaces existing books automatically

## Architecture

- **Backend**: Flask + Flask-SocketIO
- **Frontend**: HTML5 + CSS3 + Vanilla JavaScript
- **Database**: SQLite (file-based, no setup required)
- **IRC Client**: Threaded `AsyncDCCBot` with DCC support
- **Queue System**: Thread-safe FIFO queue for request management

## Installation

### Prerequisites

- Python 3.13+
- `uv` (Python package manager)

### Setup

1. **Clone or navigate to the project directory**
   ```bash
   cd /path/to/ircbot
   ```

2. **Install dependencies** (already done if you ran `uv sync`)
   ```bash
   uv sync
   ```

3. **Configure settings**
   
   Edit `config.py` to customize your installation:
   
   ```python
   # Change the password!
   APP_PASSWORD = "your_secure_password_here"
   
   # Adjust port if needed
   PORT = 5000
   
   # IRC settings (already configured)
   IRC_SERVER = "irc.irchighway.net"
   IRC_PORT = 6660
   IRC_CHANNEL = "#ebooks"
   ```

4. **Run the application**
   ```bash
   uv run python app.py
   ```

5. **Access the web interface**
   
   Open your browser and navigate to:
   ```
   http://localhost:5000
   ```
   
   Login with the password you set in `config.py`

## Usage

### Searching for Books

1. Go to the **Search** page
2. Enter a book name (e.g., "enders game")
3. Click **Search**
4. Wait for the bot to connect (if not already connected) and search
5. Results will appear grouped by bot source (e.g., Bsk, Dumbledore, GER-Borg)

### Downloading Books

1. Browse search results
2. Check the boxes next to books you want to download
3. Click **Download Selected**
4. Progress updates will show in real-time
5. Downloaded books are automatically added to your library

### Managing Your Library

1. Go to the **Library** page
2. Use the search box to find books by title or author
3. Filter by format (epub, mobi, pdf) or source
4. Sort by date, title, or size
5. Click **Download** to get the file
6. Click **Delete** to remove from library

## Project Structure

```
ircbot/
├── app.py                  # Flask application (main entry point)
├── config.py               # Configuration settings
├── models.py               # Database models
├── auth.py                 # Authentication logic
├── bot_manager.py          # IRC bot lifecycle & queue management
├── parser.py               # Search results parser
├── async_dcc_bot.py        # IRC DCC bot (existing, unchanged)
│
├── templates/              # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── search.html
│   └── library.html
│
├── static/                 # Static assets
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── socket.js       # WebSocket connection handler
│       ├── search.js       # Search page logic
│       └── library.js      # Library page logic
│
├── downloads/              # File storage
│   ├── library/            # Permanent book storage
│   └── temp/               # Temporary search results
│
├── database.db             # SQLite database (auto-created)
├── README.md               # Original async_dcc_bot README
└── WEB_INTERFACE.md        # This file
```

## Configuration Options

### Web Server

- `HOST`: Server host (default: `0.0.0.0` - all interfaces)
- `PORT`: Server port (default: `5000`)
- `SECRET_KEY`: Flask session secret key (change in production!)

### Authentication

- `APP_PASSWORD`: Password for accessing the application

### IRC Settings

- `IRC_SERVER`: IRC server hostname
- `IRC_PORT`: IRC server port (default: `6660`)
- `IRC_CHANNEL`: IRC channel to join (default: `#ebooks`)
- `IDLE_DISCONNECT_TIMEOUT`: Auto-disconnect after idle time (default: 300 seconds)

### File Storage

- `LIBRARY_DIR`: Permanent book storage (default: `./downloads/library`)
- `TEMP_DIR`: Temporary files (default: `./downloads/temp`)

### Queue Settings

- `MAX_QUEUE_SIZE`: Maximum queued requests (default: 50)
- `REQUEST_TIMEOUT`: Timeout for DCC transfers (default: 600 seconds)

## How It Works

### Search Workflow

1. User submits search query via web form
2. Request added to queue, WebSocket notifies user of queue position
3. Queue worker connects bot to IRC (with random nickname)
4. Bot sends `@Search <query>` to channel
5. SearchBot sends zip file via DCC transfer
6. Bot downloads zip, extracts, and parses results
7. Results filtered for epub/mobi/pdf files and grouped by bot
8. WebSocket emits results to client for display

### Download Workflow

1. User selects books and clicks "Download Selected"
2. Download commands added to queue
3. Bot sends each `!BotName <file>` command to channel
4. Bot receives each book via DCC transfer
5. Files moved to library directory
6. Metadata extracted and saved to database
7. WebSocket notifies client of completion

### Queue Management

- Single worker thread processes queue items one at a time
- Maintains one persistent IRC connection (while active)
- Automatically reconnects if connection drops
- Disconnects after 5 minutes of idle time
- All clients receive real-time updates via WebSocket

## Database Schema

### Books Table

- `id`: Primary key
- `title`: Book title (extracted from filename)
- `author`: Author name (if extractable)
- `filename`: Original filename
- `filepath`: Full path to file
- `file_size`: Size in bytes
- `file_format`: epub, mobi, pdf, etc.
- `bot_source`: Source bot name (e.g., "Bsk")
- `irc_command`: Original !command for reference
- `download_date`: When book was downloaded
- `search_query`: Original search query that found it

### Search History Table

- `id`: Primary key
- `query`: Search query string
- `timestamp`: When search was performed
- `status`: completed, failed, or in_progress
- `results_count`: Number of results found

## Troubleshooting

### Bot won't connect

- Check IRC server settings in `config.py`
- Ensure port 6660 is not blocked by firewall
- Try changing the IRC port to 6667 (standard) if needed

### Search times out

- Increase `REQUEST_TIMEOUT` in `config.py`
- Check that SearchBot is active in the channel
- Verify your search query format (should not start with !, @, or /)

### Downloads fail

- Check `TEMP_DIR` and `LIBRARY_DIR` have write permissions
- Ensure enough disk space available
- Check IRC connection status in navbar

### Can't access from other devices

- Change `HOST` from `127.0.0.1` to `0.0.0.0` in `config.py`
- Check firewall allows incoming connections on chosen port
- Access via `http://<your-ip>:<port>` from other devices

## Security Notes

- **Change the password** in `config.py` before deployment
- **Use HTTPS** in production (use nginx or similar as reverse proxy)
- **Don't expose directly to internet** without additional security measures
- **Keep secret key secure** - change `SECRET_KEY` to a random string

## Development

To run in development mode:

1. Set `DEBUG = True` in `config.py`
2. Run: `uv run python app.py`
3. Server will auto-reload on code changes

## Credits

Built with:
- Flask - Web framework
- Flask-SocketIO - WebSocket support
- SQLAlchemy - Database ORM
- IRC library - IRC client functionality

---

**Enjoy your IRC book downloading experience!** 📚
