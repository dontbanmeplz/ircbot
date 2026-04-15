from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    author = Column(String, nullable=False, default="Unknown")
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    format = Column(String, nullable=False, default="unknown")
    source_bot = Column(String, nullable=True)
    irc_command = Column(String, nullable=True)  # The full !bot command used
    created_at = Column(DateTime, server_default=func.now())

    downloads = relationship("Download", back_populates="book")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "filename": self.filename,
            "file_size": self.file_size,
            "format": self.format,
            "source_bot": self.source_bot,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SearchSession(Base):
    __tablename__ = "search_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")  # pending, searching, complete, failed
    results_json = Column(Text, nullable=True)  # JSON string of parsed results
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    def to_dict(self):
        import json
        results = json.loads(self.results_json) if self.results_json else []
        return {
            "id": self.id,
            "query": self.query,
            "status": self.status,
            "results": results,
            "error_message": self.error_message,
            "result_count": len(results),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Download(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False)
    ip_address = Column(String, nullable=False)
    user_agent = Column(String, nullable=True)
    downloaded_at = Column(DateTime, server_default=func.now())

    book = relationship("Book", back_populates="downloads")

    def to_dict(self):
        return {
            "id": self.id,
            "book_id": self.book_id,
            "book_title": self.book.title if self.book else None,
            "book_author": self.book.author if self.book else None,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "downloaded_at": self.downloaded_at.isoformat() if self.downloaded_at else None,
        }


class IPTag(Base):
    __tablename__ = "ip_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip_address = Column(String, nullable=False, unique=True)
    tag_name = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "ip_address": self.ip_address,
            "tag_name": self.tag_name,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SearchPreferences(Base):
    """Singleton config row for search result filtering and weighting.
    
    allowed_formats: JSON list of formats to show (e.g. ["epub"])
    weight_rules: JSON list of rules, each is:
        {"tag": "provider", "pattern": "...", "weight": 10, "label": "Preferred bot"}
    Tags are freeform categories like "provider", "quality", "language", etc.
    Weight is an integer: higher = shown first. Negative = pushed down.
    Pattern is matched against the full result line (bot name + display name).
    """
    __tablename__ = "search_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    allowed_formats = Column(Text, nullable=False, default='["epub"]')
    weight_rules = Column(Text, nullable=False, default='[]')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        import json
        return {
            "allowed_formats": json.loads(self.allowed_formats) if self.allowed_formats else ["epub"],
            "weight_rules": json.loads(self.weight_rules) if self.weight_rules else [],
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
