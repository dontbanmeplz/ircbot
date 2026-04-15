"""
Configuration file for IRC Book Downloader
Edit these settings to customize your installation
"""

# ============================================================================
# WEB SERVER SETTINGS
# ============================================================================
HOST = "0.0.0.0"              # Listen on all interfaces (change to "127.0.0.1" for local only)
PORT = 8003            # Web server port (change as needed)
DEBUG = False                 # Set to True for development

# Secret key for Flask sessions (IMPORTANT: Change this to a random string!)
SECRET_KEY = "change-thiem-secret-key-iection"

# Session timeout in seconds (default: 1 hour)
SESSION_TIMEOUT = 3600

# ============================================================================
# AUTHENTICATION
# ============================================================================
# Password for accessing the application
# IMPORTANT: Change this before deployment!
APP_PASSWORD = "admin123"

# ============================================================================
# IRC SETTINGS
# ============================================================================
IRC_SERVER = "irc.irchighway.net"
IRC_PORT = 6660               # Correct port as specified
IRC_CHANNEL = "#ebooks"
IRC_USE_SSL = False           # Set to True if using SSL

# IRC password (if required by server - usually not needed)
IRC_PASSWORD = None

# Bot nickname generation
# Bot will use format: {adjective}{noun}{number}
# Example: "SwiftReader742", "QuickSeeker319"
NICKNAME_ADJECTIVES = [
    "Swift", "Quick", "Fast", "Smart", "Wise", "Clever", 
    "Bright", "Sharp", "Keen", "Rapid", "Agile", "Bold"
]
NICKNAME_NOUNS = [
    "Reader", "Bot", "Seeker", "Hunter", "Finder", "Browser",
    "Scanner", "Searcher", "Crawler", "Explorer", "Agent"
]

# Idle disconnect timer (seconds) - bot disconnects after this time of inactivity
IDLE_DISCONNECT_TIMEOUT = 300  # 5 minutes

# ============================================================================
# FILE STORAGE
# ============================================================================
DOWNLOAD_DIR = "./downloads"
LIBRARY_DIR = "./downloads/library"
TEMP_DIR = "./downloads/temp"

# Maximum file size for web download (bytes) - 50MB default
MAX_DOWNLOAD_SIZE = 50 * 1024 * 1024

# ============================================================================
# DATABASE
# ============================================================================
DATABASE_PATH = "./database.db"
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ============================================================================
# QUEUE SETTINGS
# ============================================================================
# Maximum number of items in queue
MAX_QUEUE_SIZE = 50

# Request timeout (seconds) - how long to wait for a DCC transfer
REQUEST_TIMEOUT = 600  # 10 minutes

# ============================================================================
# SEARCH SETTINGS
# ============================================================================
# Only include these file formats in search results
ALLOWED_FORMATS = [".epub", ".mobi", ".pdf"]

# Maximum search results to display per bot
MAX_RESULTS_PER_BOT = 100
