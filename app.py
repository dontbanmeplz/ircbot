"""
IRC Book Downloader Web Interface
Flask application with WebSocket support
"""

# eventlet monkey-patching MUST happen before any other imports
import eventlet
eventlet.monkey_patch()

import os
from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, session
from flask_socketio import SocketIO, emit, join_room
from flask_login import login_user, logout_user, login_required, current_user

import config
from models import db, Book, SearchHistory
from auth import init_auth, check_password, User
from bot_manager import BotManager

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = config.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config.SQLALCHEMY_TRACK_MODIFICATIONS
app.config['PERMANENT_SESSION_LIFETIME'] = config.SESSION_TIMEOUT

# Initialize extensions
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")
init_auth(app)

# Initialize bot manager
bot_manager = None


# ============================================================================
# HTTP ROUTES
# ============================================================================

@app.route('/')
@login_required
def index():
    """Main search page"""
    return render_template('search.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        
        if check_password(password):
            user = User()
            login_user(user, remember=True)
            session.permanent = True
            
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            return render_template('login.html', error='Invalid password')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    return redirect(url_for('login'))


@app.route('/library')
@login_required
def library():
    """Library page"""
    return render_template('library.html')


@app.route('/api/library/books')
@login_required
def get_library_books():
    """Get all books in library (AJAX endpoint)"""
    try:
        # Get filter parameters
        search_query = request.args.get('q', '').strip()
        format_filter = request.args.get('format', '').strip()
        source_filter = request.args.get('source', '').strip()
        sort_by = request.args.get('sort', 'date')  # date, title, size
        
        # Build query
        query = Book.query
        
        if search_query:
            query = query.filter(
                db.or_(
                    Book.title.ilike(f'%{search_query}%'),
                    Book.author.ilike(f'%{search_query}%'),
                    Book.filename.ilike(f'%{search_query}%')
                )
            )
        
        if format_filter:
            query = query.filter(Book.file_format == format_filter)
        
        if source_filter:
            query = query.filter(Book.bot_source == source_filter)
        
        # Apply sorting
        if sort_by == 'title':
            query = query.order_by(Book.title.asc())
        elif sort_by == 'size':
            query = query.order_by(Book.file_size.desc())
        else:  # date
            query = query.order_by(Book.download_date.desc())
        
        books = query.all()
        
        return jsonify({
            'success': True,
            'books': [book.to_dict() for book in books],
            'total': len(books)
        })
        
    except Exception as e:
        print(f"Error getting library books: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/library/filters')
@login_required
def get_library_filters():
    """Get available filter options"""
    try:
        # Get unique formats
        formats = db.session.query(Book.file_format).distinct().all()
        formats = [f[0] for f in formats if f[0]]
        
        # Get unique sources
        sources = db.session.query(Book.bot_source).distinct().all()
        sources = [s[0] for s in sources if s[0]]
        
        return jsonify({
            'success': True,
            'formats': sorted(formats),
            'sources': sorted(sources)
        })
        
    except Exception as e:
        print(f"Error getting filters: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/download/<int:book_id>')
@login_required
def download_book(book_id):
    """Download a book from library"""
    try:
        book = Book.query.get_or_404(book_id)
        
        if not os.path.exists(book.filepath):
            return "File not found", 404
        
        return send_file(
            book.filepath,
            as_attachment=True,
            download_name=book.filename
        )
        
    except Exception as e:
        print(f"Error downloading book: {e}")
        return f"Error: {e}", 500


@app.route('/api/library/delete/<int:book_id>', methods=['DELETE'])
@login_required
def delete_book(book_id):
    """Delete a book from library"""
    try:
        book = Book.query.get_or_404(book_id)
        
        # Delete file
        if os.path.exists(book.filepath):
            os.remove(book.filepath)
        
        # Delete from database
        db.session.delete(book)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Book deleted successfully'
        })
        
    except Exception as e:
        print(f"Error deleting book: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stats')
@login_required
def get_stats():
    """Get library statistics"""
    try:
        total_books = Book.query.count()
        total_size = db.session.query(db.func.sum(Book.file_size)).scalar() or 0
        recent_searches = SearchHistory.query.order_by(SearchHistory.timestamp.desc()).limit(5).all()
        
        return jsonify({
            'success': True,
            'total_books': total_books,
            'total_size': total_size,
            'recent_searches': [s.to_dict() for s in recent_searches]
        })
        
    except Exception as e:
        print(f"Error getting stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ============================================================================
# WEBSOCKET HANDLERS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if not current_user.is_authenticated:
        return False  # Reject connection
    
    # Join room based on session ID
    session_id = request.sid
    join_room(session_id)
    
    print(f"Client connected: {session_id}")
    
    # Send current queue status
    emit('queue_update', {
        'size': bot_manager.request_queue.qsize(),
        'processing': bot_manager.is_processing,
        'connected': bot_manager.is_connected
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print(f"Client disconnected: {request.sid}")


@socketio.on('search')
def handle_search(data):
    """
    Handle search request
    
    Expected data: {'query': 'book name'}
    """
    if not current_user.is_authenticated:
        return
    
    query = data.get('query', '').strip()
    
    if not query:
        emit('error', {'message': 'Search query is required'})
        return
    
    # Sanitize query (prevent IRC command injection)
    if query.startswith(('@', '!', '/')):
        emit('error', {'message': 'Invalid search query'})
        return
    
    session_id = request.sid
    
    # Add to queue
    result = bot_manager.add_search_request(query, session_id)
    
    if result['success']:
        emit('status', {
            'message': result['message'],
            'type': 'info'
        })
    else:
        emit('error', {'message': result['message']})


@socketio.on('download')
def handle_download(data):
    """
    Handle download request
    
    Expected data: {
        'commands': ['!Bot file1', '!Bot file2'],
        'titles': ['Title 1', 'Title 2'],
        'query': 'original search query'
    }
    """
    if not current_user.is_authenticated:
        return
    
    commands = data.get('commands', [])
    titles = data.get('titles', [])
    query = data.get('query', '')
    
    if not commands:
        emit('error', {'message': 'No books selected'})
        return
    
    session_id = request.sid
    
    # Add to queue
    result = bot_manager.add_download_request(commands, titles, query, session_id)
    
    if result['success']:
        emit('status', {
            'message': result['message'],
            'type': 'info'
        })
    else:
        emit('error', {'message': result['message']})


@socketio.on('get_queue_status')
def handle_get_queue_status():
    """Get current queue status"""
    if not current_user.is_authenticated:
        return
    
    emit('queue_update', {
        'size': bot_manager.request_queue.qsize(),
        'processing': bot_manager.is_processing,
        'connected': bot_manager.is_connected
    })


# ============================================================================
# APPLICATION STARTUP
# ============================================================================

def init_app():
    """Initialize application"""
    global bot_manager
    
    # Create database tables
    with app.app_context():
        db.create_all()
        print("Database initialized")
    
    # Initialize bot manager
    bot_manager = BotManager(socketio, app)
    print("Bot manager initialized")
    
    # Create directories
    os.makedirs(config.LIBRARY_DIR, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    print("Directories created")


# Initialize on import so gunicorn can use the app directly
init_app()


# ============================================================================
# MAIN (for local development)
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("IRC Book Downloader Web Interface")
    print("=" * 60)
    print(f"Starting server on {config.HOST}:{config.PORT}")
    print(f"IRC Server: {config.IRC_SERVER}:{config.IRC_PORT}")
    print(f"IRC Channel: {config.IRC_CHANNEL}")
    print(f"Library Dir: {config.LIBRARY_DIR}")
    print(f"Password: {config.APP_PASSWORD}")
    print("=" * 60)
    
    # Run development server
    socketio.run(
        app,
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        allow_unsafe_werkzeug=True
    )
