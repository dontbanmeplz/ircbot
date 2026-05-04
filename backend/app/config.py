import os
from pathlib import Path

from pydantic_settings import BaseSettings

from app.nickgen import generate_nick


class Settings(BaseSettings):
    # Auth
    password: str = "changeme"
    admin_password: str = "admin"
    jwt_secret: str = "super-secret-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 72

    # IRC
    irc_server: str = "irc.irchighway.net"
    irc_port: int = 6667
    irc_use_ssl: bool = False
    irc_nick: str = ""  # Empty = auto-generate a human-looking nick
    irc_channel: str = "#ebooks"

    # Proxy
    proxy_enabled: bool = False
    proxy_list_url: str = "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.json"
    proxy_refresh_minutes: int = 30
    proxy_manual: str = ""  # Comma-separated manual proxies: ip:port,ip:port
    proxy_username: str = ""  # SOCKS5 auth username (leave blank for no auth)
    proxy_password: str = ""  # SOCKS5 auth password
    proxy_connect_timeout: int = 7  # seconds to test if a proxy is alive

    # Storage
    storage_path: Path = Path(__file__).parent.parent / "storage"
    db_path: Path = Path(__file__).parent.parent.parent / "data" / "ircbot.db"

    model_config = {"env_prefix": "IRCBOT_"}


settings = Settings()

# Auto-generate a nick if none was set
if not settings.irc_nick:
    settings.irc_nick = generate_nick()

# Ensure directories exist
settings.storage_path.mkdir(parents=True, exist_ok=True)
settings.db_path.parent.mkdir(parents=True, exist_ok=True)
