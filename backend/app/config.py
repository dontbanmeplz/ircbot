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
    irc_port: int = 6697
    irc_use_ssl: bool = True
    irc_nick: str = ""  # Empty = auto-generate a human-looking nick
    irc_channel: str = "#ebooks"

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
