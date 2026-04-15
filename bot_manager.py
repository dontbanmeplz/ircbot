"""
IRC Bot Manager
Manages IRC bot lifecycle, queue processing, and WebSocket communication
"""

import asyncio
import os
import random
import shutil
import threading
import time
from datetime import datetime
from queue import Queue, Empty
from typing import Optional, Dict, Any, Callable

import config
from async_dcc_bot import AsyncDCCBot
from parser import parse_search_results, extract_metadata_from_filename
from models import db, Book, SearchHistory


class BotManager:
    """
    Manages IRC bot connection and request queue
    Runs bot in background thread and processes requests one at a time
    """
    
    def __init__(self, socketio, app=None):
        """
        Initialize bot manager
        
        Args:
            socketio: Flask-SocketIO instance for emitting events
            app: Flask application instance (needed for db access in background threads)
        """
        self.socketio = socketio
        self.app = app
        self.bot: Optional[AsyncDCCBot] = None
        self.bot_thread: Optional[threading.Thread] = None
        self.is_connected = False
        self.is_processing = False
        self.should_stop = False
        
        # Request queue
        self.request_queue = Queue(maxsize=config.MAX_QUEUE_SIZE)
        self.current_request: Optional[Dict[str, Any]] = None
        self.queue_worker_thread: Optional[threading.Thread] = None
        
        # Idle disconnect timer
        self.last_activity_time = time.time()
        self.idle_timer_thread: Optional[threading.Thread] = None
        
        # Create directories
        os.makedirs(config.LIBRARY_DIR, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        
        # Start queue worker
        self.start_queue_worker()
        self.start_idle_timer()
    
    def generate_nickname(self) -> str:
        """Generate random nickname for IRC bot"""
        adj = random.choice(config.NICKNAME_ADJECTIVES)
        noun = random.choice(config.NICKNAME_NOUNS)
        num = random.randint(100, 999)
        return f"{adj}{noun}{num}"
    
    def emit_status(self, message: str, progress: int = 0, status_type: str = "info", session_id: str = None):
        """
        Emit status update via WebSocket
        
        Args:
            message: Status message
            progress: Progress percentage (0-100)
            status_type: Type of status (info, success, error, warning)
            session_id: Target session ID (None = broadcast to all)
        """
        data = {
            'message': message,
            'progress': progress,
            'type': status_type
        }
        
        if session_id:
            self.socketio.emit('status', data, room=session_id)
        else:
            self.socketio.emit('status', data)
    
    def emit_queue_update(self):
        """Emit queue status update to all clients"""
        queue_size = self.request_queue.qsize()
        self.socketio.emit('queue_update', {
            'size': queue_size,
            'processing': self.is_processing,
            'connected': self.is_connected
        })
    
    async def connect_bot(self):
        """Connect to IRC server"""
        if self.is_connected:
            return
        
        try:
            nickname = self.generate_nickname()
            self.emit_status(f"Connecting to IRC as {nickname}...", 0)
            
            # Create bot instance with callbacks
            self.bot = AsyncDCCBot(
                channel=config.IRC_CHANNEL,
                download_dir=config.TEMP_DIR,
                on_file_received=self.on_file_received,
                on_connected=self.on_bot_connected,
                on_message_sent=self.on_message_sent,
            )
            
            # Start bot
            await self.bot.start(
                server=config.IRC_SERVER,
                port=config.IRC_PORT,
                nickname=nickname,
                password=config.IRC_PASSWORD
            )
            
            # Wait until ready
            await self.bot.wait_until_ready(timeout=30)
            
            self.is_connected = True
            self.socketio.emit('bot_connected', {'nickname': nickname})
            self.emit_status(f"Connected as {nickname}", 100, "success")
            
        except Exception as e:
            print(f"Error connecting to IRC: {e}")
            import traceback
            traceback.print_exc()
            self.emit_status(f"Connection failed: {e}", 0, "error")
            self.is_connected = False
    
    def disconnect_bot(self):
        """Disconnect from IRC server"""
        if not self.is_connected or not self.bot:
            return
        
        try:
            self.emit_status("Disconnecting from IRC...", 0)
            self.bot.stop("Idle timeout")
            self.is_connected = False
            self.bot = None
            self.socketio.emit('bot_disconnected')
            self.emit_status("Disconnected", 100, "info")
        except Exception as e:
            print(f"Error disconnecting: {e}")
    
    def on_bot_connected(self):
        """Callback when bot connects to IRC"""
        print("Bot connected to IRC channel")
    
    def on_message_sent(self, message: str):
        """Callback when bot sends a message"""
        print(f"Bot sent: {message}")
    
    def on_file_received(self, filename: str, size: int):
        """
        Callback when bot receives a file via DCC
        
        Args:
            filename: Name of received file
            size: File size in bytes
        """
        print(f"File received: {filename} ({size} bytes)")
        
        if self.current_request:
            self.current_request['received_file'] = filename
            self.current_request['file_size'] = size
    
    def add_search_request(self, query: str, session_id: str) -> Dict[str, Any]:
        """
        Add search request to queue
        
        Args:
            query: Search query
            session_id: Session ID of requester
            
        Returns:
            dict: Request status
        """
        try:
            request = {
                'type': 'search',
                'query': query,
                'session_id': session_id,
                'status': 'queued',
                'timestamp': datetime.utcnow(),
                'received_file': None
            }
            
            self.request_queue.put(request, block=False)
            self.emit_queue_update()
            
            return {
                'success': True,
                'position': self.request_queue.qsize(),
                'message': f'Search queued for "{query}"'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Queue full or error: {e}'
            }
    
    def add_download_request(self, commands: list, titles: list, query: str, session_id: str) -> Dict[str, Any]:
        """
        Add download request to queue
        
        Args:
            commands: List of IRC commands (!Bot filename)
            titles: List of book titles (for display)
            query: Original search query
            session_id: Session ID of requester
            
        Returns:
            dict: Request status
        """
        try:
            request = {
                'type': 'download',
                'commands': commands,
                'titles': titles,
                'query': query,
                'session_id': session_id,
                'status': 'queued',
                'timestamp': datetime.utcnow(),
                'completed': 0,
                'total': len(commands)
            }
            
            self.request_queue.put(request, block=False)
            self.emit_queue_update()
            
            return {
                'success': True,
                'position': self.request_queue.qsize(),
                'message': f'Download queued for {len(commands)} books'
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Queue full or error: {e}'
            }
    
    def start_queue_worker(self):
        """Start background thread to process queue"""
        self.queue_worker_thread = threading.Thread(target=self.process_queue, daemon=True)
        self.queue_worker_thread.start()
    
    def start_idle_timer(self):
        """Start background thread to monitor idle time"""
        self.idle_timer_thread = threading.Thread(target=self.check_idle_timeout, daemon=True)
        self.idle_timer_thread.start()
    
    def check_idle_timeout(self):
        """Monitor idle time and disconnect if timeout reached"""
        while not self.should_stop:
            time.sleep(30)  # Check every 30 seconds
            
            if self.is_connected and not self.is_processing:
                idle_time = time.time() - self.last_activity_time
                if idle_time >= config.IDLE_DISCONNECT_TIMEOUT:
                    print(f"Idle timeout reached ({idle_time:.0f}s), disconnecting...")
                    self.disconnect_bot()
    
    def process_queue(self):
        """
        Background worker that processes queue items
        Runs in separate thread with its own event loop
        """
        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while not self.should_stop:
            try:
                # Get next request (blocking with timeout)
                try:
                    request = self.request_queue.get(timeout=1)
                except Empty:
                    continue
                
                self.current_request = request
                self.is_processing = True
                self.last_activity_time = time.time()
                self.emit_queue_update()
                
                # Connect if not connected
                if not self.is_connected:
                    loop.run_until_complete(self.connect_bot())
                
                # Process based on type
                if request['type'] == 'search':
                    loop.run_until_complete(self.process_search_request(request))
                elif request['type'] == 'download':
                    loop.run_until_complete(self.process_download_request(request))
                
                self.current_request = None
                self.is_processing = False
                self.last_activity_time = time.time()
                self.emit_queue_update()
                
                # Mark task as done
                self.request_queue.task_done()
                
            except Exception as e:
                print(f"Error processing queue item: {e}")
                import traceback
                traceback.print_exc()
                self.is_processing = False
                self.current_request = None
    
    async def process_search_request(self, request: Dict[str, Any]):
        """
        Process search request
        
        Args:
            request: Search request dict
        """
        query = request['query']
        session_id = request['session_id']
        
        try:
            # Send search command
            search_cmd = f"@Search {query}"
            self.emit_status(f"Searching for '{query}'...", 10, session_id=session_id)
            
            await self.bot.send_message(search_cmd)
            
            # Wait for DCC file transfer
            self.emit_status("Waiting for search results...", 30, session_id=session_id)
            
            # Poll for received file (timeout after REQUEST_TIMEOUT)
            start_time = time.time()
            while not request.get('received_file'):
                await asyncio.sleep(1)
                if time.time() - start_time > config.REQUEST_TIMEOUT:
                    raise TimeoutError("Search timed out waiting for results")
            
            # Parse results
            self.emit_status("Parsing results...", 60, session_id=session_id)
            zip_path = os.path.join(config.TEMP_DIR, request['received_file'])
            results = parse_search_results(zip_path)
            
            # Count total results
            total_results = sum(len(books) for books in results.values())
            
            # Save to database
            with self.app.app_context():
                search_history = SearchHistory(
                    query=query,
                    status='completed',
                    results_count=total_results
                )
                db.session.add(search_history)
                db.session.commit()
            
            # Emit results to client
            self.emit_status(f"Found {total_results} results", 100, "success", session_id=session_id)
            self.socketio.emit('search_results', {
                'grouped_results': results,
                'total': total_results,
                'query': query
            }, room=session_id)
            
        except Exception as e:
            print(f"Error in search: {e}")
            import traceback
            traceback.print_exc()
            self.emit_status(f"Search failed: {e}", 0, "error", session_id=session_id)
            
            # Update database
            with self.app.app_context():
                search_history = SearchHistory(
                    query=query,
                    status='failed',
                    results_count=0
                )
                db.session.add(search_history)
                db.session.commit()
    
    async def process_download_request(self, request: Dict[str, Any]):
        """
        Process download request
        
        Args:
            request: Download request dict
        """
        commands = request['commands']
        titles = request['titles']
        query = request['query']
        session_id = request['session_id']
        
        try:
            total = len(commands)
            
            for i, (command, title) in enumerate(zip(commands, titles)):
                self.emit_status(f"Downloading {i+1}/{total}: {title[:50]}...", 
                               int((i / total) * 100), session_id=session_id)
                
                # Reset received file flag
                request['received_file'] = None
                
                # Send download command
                await self.bot.send_message(command)
                
                # Wait for DCC file transfer
                start_time = time.time()
                while not request.get('received_file'):
                    await asyncio.sleep(1)
                    if time.time() - start_time > config.REQUEST_TIMEOUT:
                        raise TimeoutError(f"Download timed out for {title}")
                
                # Process received file
                filename = request['received_file']
                temp_path = os.path.join(config.TEMP_DIR, filename)
                
                # Move to library
                library_path = os.path.join(config.LIBRARY_DIR, filename)
                
                # Check if file already exists (replace mode)
                with self.app.app_context():
                    existing_book = Book.query.filter_by(filename=filename).first()
                    if existing_book:
                        # Remove old file
                        if os.path.exists(existing_book.filepath):
                            os.remove(existing_book.filepath)
                        
                        # Update record
                        existing_book.filepath = library_path
                        existing_book.download_date = datetime.utcnow()
                        existing_book.search_query = query
                        
                        shutil.move(temp_path, library_path)
                        db.session.commit()
                        
                        book_id = existing_book.id
                    else:
                        # Create new record
                        shutil.move(temp_path, library_path)
                        
                        # Extract metadata
                        metadata = extract_metadata_from_filename(filename)
                        
                        # Extract bot name from command
                        bot_name = command.split()[0][1:]  # Remove '!'
                        
                        # Get file info
                        file_size = os.path.getsize(library_path)
                        file_format = os.path.splitext(filename)[1][1:]  # Remove '.'
                        
                        # Create book record
                        book = Book(
                            title=metadata['title'],
                            author=metadata['author'],
                            filename=filename,
                            filepath=library_path,
                            file_size=file_size,
                            file_format=file_format,
                            bot_source=bot_name,
                            irc_command=command,
                            search_query=query
                        )
                        
                        db.session.add(book)
                        db.session.commit()
                        
                        book_id = book.id
                
                # Emit download complete
                self.socketio.emit('download_complete', {
                    'book_id': book_id,
                    'title': title,
                    'filename': filename,
                    'progress': int(((i + 1) / total) * 100)
                }, room=session_id)
            
            self.emit_status(f"Downloaded {total} books successfully", 100, "success", session_id=session_id)
            
        except Exception as e:
            print(f"Error in download: {e}")
            import traceback
            traceback.print_exc()
            self.emit_status(f"Download failed: {e}", 0, "error", session_id=session_id)
    
    def stop(self):
        """Stop bot manager and cleanup"""
        self.should_stop = True
        if self.is_connected:
            self.disconnect_bot()
