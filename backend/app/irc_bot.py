"""IRC bot that connects to irchighway #ebooks and handles search/download via DCC.

Runs in a background thread. Communicates with FastAPI via thread-safe queues.
Uses jaraco/irc library with select-based reactor for DCC compatibility.
"""

import json
import logging
import os
import random
import re
import ssl
import string
import struct
import socket
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from queue import Queue, Empty
from typing import Optional

import irc.client
import irc.connection

from app.config import settings
from app.nickgen import generate_nick, random_version_string
from app.dcc import (
    DCCSendOffer,
    parse_dcc_send,
    receive_dcc_file,
    extract_search_results,
    parse_search_results,
)

logger = logging.getLogger("ircbot")


class JobType(Enum):
    SEARCH = "search"
    DOWNLOAD = "download"


@dataclass
class SearchJob:
    session_id: int
    query: str


@dataclass
class DownloadJob:
    book_command: str  # e.g. "!BotName Author - Title.epub"
    session_id: Optional[int] = None


@dataclass 
class SearchComplete:
    session_id: int
    results: list[dict]
    error: Optional[str] = None


@dataclass
class DownloadComplete:
    book_command: str
    filepath: Optional[Path] = None
    filename: Optional[str] = None
    filesize: int = 0
    error: Optional[str] = None
    session_id: Optional[int] = None


class IRCBookBot:
    """IRC bot for searching and downloading books from irchighway #ebooks.
    
    Thread-safe: accepts jobs via queues, posts results back via queues.
    Runs the irc library's select-based reactor in its own thread.
    """

    def __init__(self):
        self.server = settings.irc_server
        self.port = settings.irc_port
        self.use_ssl = settings.irc_use_ssl
        self.nick = settings.irc_nick
        self.channel = settings.irc_channel
        self.storage_path = settings.storage_path

        # Thread-safe queues for communication with FastAPI
        self.search_queue: Queue[SearchJob] = Queue()
        self.download_queue: Queue[DownloadJob] = Queue()
        self.search_results: Queue[SearchComplete] = Queue()
        self.download_results: Queue[DownloadComplete] = Queue()

        # Internal state
        self._reactor: Optional[irc.client.Reactor] = None
        self._connection: Optional[irc.client.ServerConnection] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._connected = False
        self._joined = False

        # Pending operations
        self._pending_search: Optional[SearchJob] = None
        self._pending_download: Optional[DownloadJob] = None
        self._active_dcc_downloads: dict[str, DownloadJob] = {}

    @property
    def is_connected(self) -> bool:
        return self._connected and self._joined

    @property
    def status(self) -> dict:
        return {
            "connected": self._connected,
            "joined": self._joined,
            "server": self.server,
            "channel": self.channel,
            "nick": self.nick,
            "pending_search": self._pending_search is not None,
            "pending_download": self._pending_download is not None,
        }

    def start(self):
        """Start the bot in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="irc-bot")
        self._thread.start()
        logger.info("IRC bot thread started")

    def stop(self):
        """Stop the bot."""
        self._running = False
        if self._connection:
            try:
                self._connection.quit("Goodbye")
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("IRC bot stopped")

    def submit_search(self, job: SearchJob):
        """Submit a search job (thread-safe)."""
        self.search_queue.put(job)

    def submit_download(self, job: DownloadJob):
        """Submit a download job (thread-safe)."""
        self.download_queue.put(job)

    def _run(self):
        """Main bot loop - runs in background thread."""
        while self._running:
            try:
                self._connect_and_run()
            except Exception as e:
                logger.error(f"IRC bot error: {e}", exc_info=True)
                self._connected = False
                self._joined = False

            if self._running:
                logger.info("Reconnecting in 10 seconds...")
                time.sleep(10)

    def _connect_and_run(self):
        """Connect to IRC and run the event loop."""
        # Generate a fresh nick for each connection attempt
        self.nick = generate_nick()
        logger.info(f"Using nick: {self.nick}")

        self._reactor = irc.client.Reactor()

        # Register event handlers
        self._reactor.add_global_handler("welcome", self._on_welcome)
        self._reactor.add_global_handler("join", self._on_join)
        self._reactor.add_global_handler("privmsg", self._on_privmsg)
        self._reactor.add_global_handler("privnotice", self._on_notice)
        self._reactor.add_global_handler("pubmsg", self._on_pubmsg)
        self._reactor.add_global_handler("ctcp", self._on_ctcp)
        self._reactor.add_global_handler("disconnect", self._on_disconnect)
        self._reactor.add_global_handler("nicknameinuse", self._on_nick_in_use)

        # Connect with SSL if configured
        connect_factory = None
        if self.use_ssl:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            connect_factory = irc.connection.Factory(wrapper=ssl_ctx.wrap_socket)

        server = self._reactor.server()
        self._connection = server
        server.connect(
            self.server,
            self.port,
            self.nick,
            connect_factory=connect_factory,
        )
        self._connected = True
        logger.info(f"Connected to {self.server}:{self.port}")

        # Event loop - process IRC events and check our job queues
        while self._running and self._connected:
            self._reactor.process_once(timeout=0.2)
            self._check_queues()

    def _check_queues(self):
        """Check job queues and dispatch work. Called from the event loop."""
        if not self._joined:
            return

        # Check for search jobs
        if self._pending_search is None:
            try:
                job = self.search_queue.get_nowait()
                self._start_search(job)
            except Empty:
                pass

        # Check for download jobs
        if self._pending_download is None:
            try:
                job = self.download_queue.get_nowait()
                self._start_download(job)
            except Empty:
                pass

    def _start_search(self, job: SearchJob):
        """Send a search query to #ebooks."""
        self._pending_search = job
        search_cmd = f"@search {job.query}"
        logger.info(f"Searching: {search_cmd}")
        self._connection.privmsg(self.channel, search_cmd)

    def _start_download(self, job: DownloadJob):
        """Send a download command to #ebooks."""
        self._pending_download = job
        logger.info(f"Requesting download: {job.book_command}")
        self._connection.privmsg(self.channel, job.book_command)

    # --- IRC Event Handlers ---

    def _on_welcome(self, connection, event):
        """Connected to server, join the channel after a short delay."""
        logger.info("Received welcome from server")
        # Need a brief delay before joining
        time.sleep(2)
        connection.join(self.channel)

    def _on_join(self, connection, event):
        """Successfully joined a channel."""
        if event.target == self.channel:
            self._joined = True
            logger.info(f"Joined {self.channel}")

    def _on_nick_in_use(self, connection, event):
        """Nickname is taken, pick a completely new human-looking nick."""
        new_nick = generate_nick()
        self.nick = new_nick
        connection.nick(new_nick)
        logger.warning(f"Nick in use, trying: {new_nick}")

    def _on_disconnect(self, connection, event):
        """Disconnected from server."""
        self._connected = False
        self._joined = False
        logger.warning("Disconnected from IRC server")

    def _on_notice(self, connection, event):
        """Handle NOTICE messages (search bot acknowledgments, etc.)."""
        msg = event.arguments[0] if event.arguments else ""
        source = event.source.nick if event.source else "unknown"
        logger.debug(f"NOTICE from {source}: {msg}")

        # Check for search-related notices
        if self._pending_search:
            lower = msg.lower()
            if "sorry" in lower and "no results" in lower:
                search = self._pending_search
                self._pending_search = None
                self.search_results.put(SearchComplete(
                    session_id=search.session_id,
                    results=[],
                    error="No results found",
                ))

    def _on_pubmsg(self, connection, event):
        """Handle public messages in channels."""
        pass  # We don't need to process channel messages

    def _on_privmsg(self, connection, event):
        """Handle private messages - DCC SEND offers arrive here."""
        msg = event.arguments[0] if event.arguments else ""
        source = event.source.nick if event.source else "unknown"

        # Check for CTCP DCC SEND (it can arrive as privmsg with \x01 wrapping)
        if "\x01" in msg:
            ctcp_msg = msg.strip("\x01")
            if ctcp_msg.startswith("DCC SEND"):
                self._handle_dcc_send(ctcp_msg, source)
                return

        logger.debug(f"PRIVMSG from {source}: {msg}")

    def _on_ctcp(self, connection, event):
        """Handle CTCP messages - VERSION queries and DCC SEND."""
        ctcp_type = event.arguments[0] if event.arguments else ""
        ctcp_data = event.arguments[1] if len(event.arguments) > 1 else ""
        source = event.source.nick if event.source else "unknown"

        if ctcp_type.upper() == "VERSION":
            connection.ctcp_reply(source, f"VERSION {random_version_string()}")
            return

        if ctcp_type.upper() == "DCC":
            self._handle_dcc_send(f"DCC {ctcp_data}", source)
            return

        logger.debug(f"CTCP {ctcp_type} from {source}: {ctcp_data}")

    def _handle_dcc_send(self, message: str, source: str):
        """Handle a DCC SEND offer - download the file."""
        logger.info(f"DCC SEND from {source}: {message}")

        offer = parse_dcc_send(message)
        if not offer:
            logger.warning(f"Failed to parse DCC SEND: {message}")
            return

        logger.info(f"DCC offer: {offer.filename} ({offer.filesize} bytes) from {offer.ip}:{offer.port}")

        if offer.is_search_result:
            self._handle_search_result_dcc(offer)
        else:
            self._handle_book_dcc(offer, source)

    def _handle_search_result_dcc(self, offer: DCCSendOffer):
        """Receive and parse a search results file via DCC."""
        if not self._pending_search:
            logger.warning("Received search results but no pending search")
            return

        search = self._pending_search
        self._pending_search = None

        def _do_receive():
            try:
                filepath = receive_dcc_file(offer, self.storage_path)
                logger.info(f"Search results downloaded: {filepath}")

                text = extract_search_results(filepath)
                results = parse_search_results(text)

                logger.info(f"Parsed {len(results)} results for query '{search.query}'")

                self.search_results.put(SearchComplete(
                    session_id=search.session_id,
                    results=[r.to_dict() for r in results],
                ))

                # Clean up the results file
                try:
                    filepath.unlink()
                except Exception:
                    pass

            except Exception as e:
                logger.error(f"Failed to receive search results: {e}", exc_info=True)
                self.search_results.put(SearchComplete(
                    session_id=search.session_id,
                    results=[],
                    error=str(e),
                ))

        # Run DCC receive in a separate thread to not block the IRC event loop
        t = threading.Thread(target=_do_receive, daemon=True)
        t.start()

    def _handle_book_dcc(self, offer: DCCSendOffer, source: str):
        """Receive a book file via DCC."""
        download = self._pending_download
        if download is None:
            logger.warning("Received book DCC but no pending download")
            # Still download it
            download = DownloadJob(book_command=f"unknown from {source}")

        self._pending_download = None

        def _do_receive():
            try:
                filepath = receive_dcc_file(offer, self.storage_path)
                logger.info(f"Book downloaded: {filepath} ({offer.filesize} bytes)")

                self.download_results.put(DownloadComplete(
                    book_command=download.book_command,
                    filepath=filepath,
                    filename=offer.filename,
                    filesize=offer.filesize,
                    session_id=download.session_id,
                ))

            except Exception as e:
                logger.error(f"Failed to receive book: {e}", exc_info=True)
                self.download_results.put(DownloadComplete(
                    book_command=download.book_command,
                    error=str(e),
                    session_id=download.session_id,
                ))

        t = threading.Thread(target=_do_receive, daemon=True)
        t.start()


# Singleton bot instance
bot = IRCBookBot()
