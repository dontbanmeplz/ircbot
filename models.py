"""
Database models for IRC Book Downloader
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Book(db.Model):
    """Represents a book in the library"""
    __tablename__ = 'books'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False, index=True)
    author = db.Column(db.String(200), index=True)
    filename = db.Column(db.String(500), unique=True, nullable=False)
    filepath = db.Column(db.String(1000), nullable=False)
    file_size = db.Column(db.Integer)  # Size in bytes
    file_format = db.Column(db.String(10))  # epub, mobi, pdf
    bot_source = db.Column(db.String(50), index=True)  # e.g., "Bsk", "Dumbledore"
    irc_command = db.Column(db.Text)  # Original !command
    download_date = db.Column(db.DateTime, default=datetime.utcnow)
    search_query = db.Column(db.String(200), index=True)  # What search found it
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'filename': self.filename,
            'file_size': self.file_size,
            'file_format': self.file_format,
            'bot_source': self.bot_source,
            'download_date': self.download_date.isoformat() if self.download_date else None,
            'search_query': self.search_query
        }


class SearchHistory(db.Model):
    """Track search history"""
    __tablename__ = 'search_history'
    
    id = db.Column(db.Integer, primary_key=True)
    query = db.Column(db.String(200), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20))  # completed, failed, in_progress
    results_count = db.Column(db.Integer)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'query': self.query,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'results_count': self.results_count
        }
