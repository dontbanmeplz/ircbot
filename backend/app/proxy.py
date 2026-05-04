"""SOCKS5 proxy manager for IRC and DCC connections.

Fetches free proxy lists, validates them (including IRC ban detection),
rotates through working ones, and provides socket factories.

Key reliability features:
  - Parallel proxy testing: tests 10 proxies at once via ThreadPoolExecutor
  - IRC-level ban detection: reads initial server response to filter banned IPs
  - Last-known-good caching: remembers working proxies and tries them first
  - Failed proxy cooldown: banned/dead proxies are skipped for 10 minutes

Uses PySocks (socks.socksocket) which is a drop-in socket.socket subclass,
compatible with select().
"""

import json
import logging
import random
import socket
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

import socks

from app.config import settings

logger = logging.getLogger("ircbot.proxy")


@dataclass
class Proxy:
    ip: str
    port: int
    last_failed: float = 0.0
    fail_count: int = 0
    last_success: float = 0.0  # monotonic timestamp of last successful connection

    def __str__(self):
        return f"{self.ip}:{self.port}"


# Strings that indicate the proxy's IP is banned on IRC
_BAN_PATTERNS = [
    "banned",
    "k-lined",
    "k-line",
    "g-lined",
    "g-line",
    "z-lined",
    "z-line",
    "denied",
    "access denied",
    "you are not welcome",
]

# Strings that indicate the server is processing us normally (not banned)
_OK_PATTERNS = [
    "looking up your hostname",
    "found your hostname",
    "could not resolve",
    "using your ip",
    "welcome to",
    "*** checking ident",
]

PROXY_FAIL_COOLDOWN = 600  # 10 minutes
PARALLEL_TEST_WORKERS = 10  # test this many proxies at once
BAN_CHECK_TIMEOUT = 3       # seconds to wait for IRC ban/ok response


class ProxyManager:
    """Manages a pool of SOCKS5 proxies with health checking and rotation."""

    def __init__(self):
        self._proxies: list[Proxy] = []
        self._last_fetch: float = 0.0
        self._current_proxy: Optional[Proxy] = None
        self._last_good: list[Proxy] = []  # recently-working proxies, tried first

    @property
    def current_proxy(self) -> Optional[Proxy]:
        return self._current_proxy

    @property
    def proxy_count(self) -> int:
        return len(self._proxies)

    def mark_current_good(self):
        """Call when the current proxy successfully joined IRC. Caches it."""
        if self._current_proxy:
            self._current_proxy.last_success = time.monotonic()
            if self._current_proxy not in self._last_good:
                self._last_good.insert(0, self._current_proxy)
                # Keep at most 5 cached good proxies
                self._last_good = self._last_good[:5]

    def refresh_if_needed(self):
        """Fetch proxy list if stale or empty."""
        if not settings.proxy_enabled:
            return

        now = time.monotonic()
        refresh_interval = settings.proxy_refresh_minutes * 60

        if self._proxies and (now - self._last_fetch) < refresh_interval:
            return

        self._fetch_proxies()

    def _fetch_proxies(self):
        """Fetch and parse proxy list from URL or manual config."""
        proxies = []

        # Manual proxies take priority
        if settings.proxy_manual:
            for entry in settings.proxy_manual.split(","):
                entry = entry.strip()
                if ":" in entry:
                    ip, port_str = entry.rsplit(":", 1)
                    try:
                        proxies.append(Proxy(ip=ip.strip(), port=int(port_str)))
                    except ValueError:
                        logger.warning(f"Invalid manual proxy: {entry}")
            if proxies:
                logger.info(f"Loaded {len(proxies)} manual proxies")
                random.shuffle(proxies)
                self._proxies = proxies
                self._last_fetch = time.monotonic()
                return

        # Fetch from URL
        url = settings.proxy_list_url
        logger.info(f"Fetching proxy list from {url}")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())

            for entry in data:
                if entry.get("protocol") == "socks5":
                    ip = entry.get("ip", "")
                    port = entry.get("port", 0)
                    if ip and port:
                        proxies.append(Proxy(ip=ip, port=int(port)))

            if proxies:
                random.shuffle(proxies)
                self._proxies = proxies
                self._last_fetch = time.monotonic()
                logger.info(f"Loaded {len(proxies)} SOCKS5 proxies")
            else:
                logger.warning("Proxy list fetch returned no SOCKS5 proxies")

        except Exception as e:
            logger.error(f"Failed to fetch proxy list: {e}")
            if not self._proxies:
                logger.error("No proxies available at all")

    def _is_available(self, proxy: Proxy) -> bool:
        """Check if a proxy is not in cooldown from recent failure."""
        if proxy.last_failed == 0.0:
            return True
        elapsed = time.monotonic() - proxy.last_failed
        return elapsed > PROXY_FAIL_COOLDOWN

    def _mark_failed(self, proxy: Proxy):
        """Mark a proxy as recently failed."""
        proxy.last_failed = time.monotonic()
        proxy.fail_count += 1
        # Remove from last-good cache if present
        self._last_good = [p for p in self._last_good if p is not proxy]

    def _configure_socket(self, proxy: Proxy) -> socks.socksocket:
        """Create and configure a SOCKS5 socket with optional auth."""
        sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
        sock.set_proxy(
            socks.SOCKS5,
            proxy.ip,
            proxy.port,
            username=settings.proxy_username or None,
            password=settings.proxy_password or None,
        )
        return sock

    def _test_proxy(self, proxy: Proxy) -> bool:
        """Full IRC-level health check: connect via SOCKS5 and verify not banned.
        
        1. SOCKS5 connect to IRC server
        2. Read initial server messages (IRC sends NOTICEs immediately)
        3. Check for ban notices - if banned, mark failed
        4. If we see normal hostname lookup notices, the proxy is clean
        """
        sock = None
        try:
            sock = self._configure_socket(proxy)
            sock.settimeout(settings.proxy_connect_timeout)
            sock.connect((settings.irc_server, settings.irc_port))

            # Read the first messages from the IRC server.
            sock.settimeout(BAN_CHECK_TIMEOUT)
            buf = b""
            try:
                while len(buf) < 4096:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    buf += chunk

                    text = buf.decode("utf-8", errors="replace").lower()

                    # Check for ban
                    for pattern in _BAN_PATTERNS:
                        if pattern in text:
                            logger.info(f"Proxy {proxy} BANNED")
                            self._mark_failed(proxy)
                            return False

                    # Check for normal response
                    for pattern in _OK_PATTERNS:
                        if pattern in text:
                            return True

            except socket.timeout:
                if buf:
                    text = buf.decode("utf-8", errors="replace").lower()
                    for pattern in _BAN_PATTERNS:
                        if pattern in text:
                            logger.info(f"Proxy {proxy} BANNED")
                            self._mark_failed(proxy)
                            return False
                return True

            return True

        except Exception as e:
            logger.debug(f"Proxy {proxy} failed: {e}")
            self._mark_failed(proxy)
            return False
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    def get_working_proxy(self) -> Optional[Proxy]:
        """Find a working proxy using parallel testing.
        
        1. Try last-known-good proxies first (sequentially, they're fast)
        2. Then test batches of proxies in parallel
        
        Returns None if no working proxy is found.
        """
        self.refresh_if_needed()

        if not self._proxies:
            logger.error("No proxies loaded")
            return None

        # First: try last-known-good proxies (fast path)
        for proxy in list(self._last_good):
            if self._is_available(proxy):
                logger.info(f"Testing cached good proxy {proxy}...")
                if self._test_proxy(proxy):
                    logger.info(f"Cached proxy {proxy} still works")
                    self._current_proxy = proxy
                    return proxy
                else:
                    logger.info(f"Cached proxy {proxy} no longer works")

        # Second: parallel test from the full pool
        available = [p for p in self._proxies if self._is_available(p)]
        if not available:
            logger.warning("All proxies in cooldown, resetting")
            for p in self._proxies:
                p.last_failed = 0.0
            available = self._proxies[:]

        random.shuffle(available)

        # Test in batches of PARALLEL_TEST_WORKERS
        max_total = min(60, len(available))
        tested = 0

        while tested < max_total:
            batch = available[tested:tested + PARALLEL_TEST_WORKERS]
            if not batch:
                break
            tested += len(batch)

            logger.info(f"Testing batch of {len(batch)} proxies ({tested}/{max_total})...")

            with ThreadPoolExecutor(max_workers=PARALLEL_TEST_WORKERS) as executor:
                futures = {
                    executor.submit(self._test_proxy, proxy): proxy
                    for proxy in batch
                }

                for future in as_completed(futures):
                    proxy = futures[future]
                    try:
                        if future.result():
                            # Found a working one - cancel the rest
                            logger.info(f"Proxy {proxy} is working")
                            self._current_proxy = proxy
                            # Cancel remaining futures (best effort)
                            for f in futures:
                                f.cancel()
                            return proxy
                    except Exception:
                        pass

        logger.error(f"No working proxy found after testing {tested} proxies")
        return None

    def create_irc_connection(self, server: str, port: int) -> socket.socket:
        """Create a fully connected IRC socket through a proxy.
        
        Args:
            server: IRC server hostname
            port: IRC server port
            
        Returns:
            Connected socket tunneled through the SOCKS5 proxy.
        """
        proxy = self._current_proxy
        if not proxy:
            raise RuntimeError("No proxy available for IRC connection")

        sock = self._configure_socket(proxy)
        sock.settimeout(30)

        logger.info(f"Connecting to {server}:{port} via proxy {proxy}")
        sock.connect((server, port))

        return sock


# Singleton
proxy_manager = ProxyManager()
