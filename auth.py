"""
Authentication module for IRC Book Downloader
Simple password-based authentication using Flask-Login
"""

from flask_login import LoginManager, UserMixin
import config

# Initialize Flask-Login
login_manager = LoginManager()


class User(UserMixin):
    """Simple user class for authentication"""
    def __init__(self, id='user'):
        self.id = id


def init_auth(app):
    """Initialize authentication for the Flask app"""
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please login to access this page.'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID"""
        return User(user_id)


def check_password(password):
    """
    Check if provided password matches the configured password
    
    Args:
        password: Password to check
        
    Returns:
        bool: True if password is correct
    """
    return password == config.APP_PASSWORD
