#!/usr/bin/env python3
"""
Async IRC bot with DCC file transfer support.
Uses synchronous IRC client in a thread for DCC compatibility.

NOTE: The async version of irc.client_aio does NOT support DCC transfers.
This implementation uses the synchronous irc.client in a background thread
to enable full DCC support while maintaining an async-friendly API.
"""

import asyncio
import os
import shlex
import struct
import sys
import threading
from typing import Optional, Callable

import irc.client


class AsyncDCCBot(irc.client.SimpleIRCClient):
    """
    An IRC bot that can send messages and receive files via DCC.
    Runs the IRC client in a background thread to maintain async compatibility.
    
    Example usage:
        bot = AsyncDCCBot(
            channel="#mychannel",
            on_file_received=lambda filename, size: print(f"Got {filename}!")
        )
        
        # Start bot
        await bot.start("irc.server.net", 6667, "MyBot")
        
        # Wait until ready
        await bot.wait_until_ready()
        
        # Send a message
        await bot.send_message("Hello, world!")
    """
    
    def __init__(
        self,
        channel: str,
        download_dir: str = "./downloads",
        on_file_received: Optional[Callable[[str, int], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_message_sent: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the async DCC bot.
        
        Args:
            channel: IRC channel to join (e.g., "#mychannel")
            download_dir: Directory to save received files
            on_file_received: Callback when file is received (filename, size)
            on_connected: Callback when connected and joined channel
            on_message_sent: Callback when message is sent (message)
        """
        super().__init__()
        self.channel = channel
        self.download_dir = download_dir
        self.on_file_received_callback = on_file_received
        self.on_connected_callback = on_connected
        self.on_message_sent_callback = on_message_sent
        
        # DCC transfer state
        self.current_file = None
        self.current_filename = None
        self.received_bytes = 0
        self.dcc_connection = None
        
        # Connection state
        self.is_connected = False
        self.is_joined = False
        self._should_stop = False
        self._thread = None
        
        # Create download directory if it doesn't exist
        os.makedirs(self.download_dir, exist_ok=True)
    
    def on_welcome(self, connection, event):
        """Called when connected to the IRC server."""
        print(f"Connected to {connection.get_server_name()}")
        if irc.client.is_channel(self.channel):
            connection.join(self.channel)
        self.is_connected = True
    
    def on_join(self, connection, event):
        """Called when successfully joined a channel."""
        print(f"Joined {self.channel}")
        self.is_joined = True
        if self.on_connected_callback:
            self.on_connected_callback()
    
    def on_disconnect(self, connection, event):
        """Called when disconnected from the IRC server."""
        print("Disconnected from server")
        self.is_connected = False
        self.is_joined = False
    
    def on_pubmsg(self, connection, event):
        """Called when a public message is received in a channel."""
        source = event.source.nick
        message = event.arguments[0]
        print(f"[{self.channel}] <{source}> {message}")
    
    def on_ctcp(self, connection, event):
        """
        Called when a CTCP message is received.
        Handles DCC SEND requests.
        """
        payload = event.arguments[1]
        parts = shlex.split(payload)
        
        if len(parts) < 5:
            print(f"Invalid CTCP payload: {payload}")
            return
        
        command = parts[0]
        if command != "SEND":
            return
        
        filename, peer_address, peer_port, size = parts[1:5]
        self.current_filename = os.path.basename(filename)
        
        # Full path for the downloaded file
        filepath = os.path.join(self.download_dir, self.current_filename)
        
        # Check if file already exists
        if os.path.exists(filepath):
            print(f"File {self.current_filename} already exists, adding suffix")
            base, ext = os.path.splitext(self.current_filename)
            counter = 1
            while os.path.exists(filepath):
                self.current_filename = f"{base}_{counter}{ext}"
                filepath = os.path.join(self.download_dir, self.current_filename)
                counter += 1
        
        print(f"Accepting DCC SEND: {self.current_filename} ({size} bytes)")
        self.current_file = open(filepath, "wb")
        self.received_bytes = 0
        
        # Convert IP and port
        peer_address = irc.client.ip_numstr_to_quad(peer_address)
        peer_port = int(peer_port)
        
        print(f"Connecting to {peer_address}:{peer_port} for DCC transfer")
        
        # Connect to DCC peer
        self.dcc_connection = self.dcc_connect(peer_address, peer_port, "raw")
    
    def on_dccmsg(self, connection, event):
        """
        Called when DCC data is received.
        Writes data to file and sends acknowledgment.
        """
        if not self.current_file:
            print("Warning: Received DCC data but no file is open")
            return
            
        data = event.arguments[0]
        self.current_file.write(data)
        self.received_bytes += len(data)
        
        # Send acknowledgment of received bytes
        connection.send_bytes(struct.pack("!I", self.received_bytes))
        
        # Print progress
        if self.received_bytes % (1024 * 100) == 0:  # Every 100KB
            print(f"Received: {self.received_bytes / 1024:.1f} KB...")
    
    def on_dcc_disconnect(self, connection, event):
        """Called when DCC connection is closed."""
        if self.current_file:
            self.current_file.close()
            print(f"File transfer complete: {self.current_filename} ({self.received_bytes} bytes)")
            
            if self.on_file_received_callback:
                self.on_file_received_callback(self.current_filename, self.received_bytes)
            
            # Reset state
            self.current_file = None
            self.current_filename = None
            self.received_bytes = 0
            self.dcc_connection = None
    
    def _run_in_thread(self, server: str, port: int, nickname: str, password: Optional[str]):
        """Run the IRC client in a thread."""
        try:
            # Connect to server
            self.connect(server, port, nickname, password=password)
            
            # Set encoding error handling
            self.connection.buffer.errors = 'replace'
            
            # Run the reactor loop (this blocks)
            self.reactor.process_forever()
            
        except irc.client.ServerConnectionError as e:
            print(f"Connection error: {e}")
        except Exception as e:
            print(f"Error in IRC thread: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._should_stop = True
    
    async def start(
        self,
        server: str,
        port: int,
        nickname: str,
        password: Optional[str] = None,
    ):
        """
        Connect to IRC server and start the bot.
        
        Args:
            server: IRC server hostname
            port: IRC server port
            nickname: Bot nickname
            password: Server password (optional)
        """
        self._should_stop = False
        
        # Start IRC client in a background thread
        self._thread = threading.Thread(
            target=self._run_in_thread,
            args=(server, port, nickname, password),
            daemon=True
        )
        self._thread.start()
        
        # Give it a moment to start
        await asyncio.sleep(0.5)
    
    async def send_message(self, message: str):
        """
        Send a message to the channel.
        
        Args:
            message: The message to send
        """
        if not self.is_connected or not self.is_joined:
            raise RuntimeError("Not connected or not joined to channel")
        
        self.connection.privmsg(self.channel, message)
        print(f"Sent: {message}")
        
        if self.on_message_sent_callback:
            self.on_message_sent_callback(message)
        
        # Yield control to allow other async operations
        await asyncio.sleep(0)
    
    async def wait_until_ready(self, timeout: float = 30.0):
        """
        Wait until bot is connected and joined to channel.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Raises:
            asyncio.TimeoutError: If connection times out
        """
        start_time = asyncio.get_event_loop().time()
        while not (self.is_connected and self.is_joined):
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise asyncio.TimeoutError("Timed out waiting for connection")
            await asyncio.sleep(0.1)
    
    def stop(self, message: str = "Goodbye!"):
        """
        Stop the bot and disconnect from the IRC server.
        
        Args:
            message: Quit message
        """
        self._should_stop = True
        if self.connection and self.is_connected:
            self.connection.disconnect(message)


async def example_usage():
    """Example of how to use the AsyncDCCBot."""
    
    def on_file_received(filename, size):
        print(f"\n=== FILE RECEIVED ===")
        print(f"Filename: {filename}")
        print(f"Size: {size} bytes ({size / 1024 / 1024:.2f} MB)")
        print(f"===================\n")
    
    def on_connected():
        print("Bot is ready!")
    
    def on_message_sent(message):
        print(f"Message sent: {message}")
    
    # Create bot instance
    bot = AsyncDCCBot(
        channel="#ebooks",
        download_dir="./downloads",
        on_file_received=on_file_received,
        on_connected=on_connected,
        on_message_sent=on_message_sent,
    )
    
    # Start bot
    await bot.start(
        server="irc.irchighway.net",
        port=6667,
        nickname="MyDCCBot789",
    )
    
    # Wait until connected and joined
    try:
        await bot.wait_until_ready(timeout=30)
    except asyncio.TimeoutError:
        print("Failed to connect within timeout")
        return
    
    # Send some messages
    await bot.send_message("Hello from DCC bot!")
    await asyncio.sleep(2)
    
    # Example: Search for a file
    await bot.send_message("@search enders game")
    
    # Keep bot running to receive files
    print("\nBot is running. Waiting for DCC transfers...")
    print("The bot will automatically download any files sent via DCC.")
    print("Press Ctrl+C to stop.\n")
    
    try:
        await asyncio.sleep(600)  # Run for 10 minutes
    except asyncio.CancelledError:
        pass
    
    # Stop
    bot.stop("Shutting down")
    await asyncio.sleep(1)


if __name__ == "__main__":
    # Run the example
    try:
        asyncio.run(example_usage())
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
