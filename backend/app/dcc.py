"""DCC SEND parser and raw TCP file receiver.

Handles the low-level protocol for receiving files over DCC from IRC bots.
irchighway DCC quirks:
  - No EOF: server does NOT close connection, must track bytes vs declared size
  - Integer IP: sent as big-endian 32-bit unsigned int
  - Filename quoting: may or may not be wrapped in double quotes
  - Search results may be .txt.zip compressed
"""

import io
import logging
import re
import socket
import struct
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import socks

logger = logging.getLogger("ircbot.dcc")

# Regex for DCC SEND: handles both quoted and unquoted filenames
DCC_SEND_RE = re.compile(
    r'DCC SEND "?(.+?)"?\s+(\d+)\s+(\d+)\s+(\d+)'
)

# Timeouts
DCC_CONNECT_TIMEOUT = 30      # seconds to establish TCP connection
DCC_READ_TIMEOUT = 60         # seconds to wait for each chunk of data
DCC_TOTAL_TIMEOUT = 300       # seconds max for an entire transfer (5 min)
DCC_SEARCH_TOTAL_TIMEOUT = 60 # seconds max for search results (smaller files)


@dataclass
class DCCSendOffer:
    """Parsed DCC SEND offer."""
    filename: str
    ip: str
    port: int
    filesize: int

    @property
    def is_search_result(self) -> bool:
        """Check if this is a search results file (not a book)."""
        return "_results_for_" in self.filename.lower() or "searchresult" in self.filename.lower()


def parse_dcc_send(message: str) -> Optional[DCCSendOffer]:
    """Parse a CTCP DCC SEND message into a DCCSendOffer.
    
    Example message: DCC SEND "SearchBot_results_for_tolkien.txt.zip" 3232235521 4500 12345
    """
    match = DCC_SEND_RE.search(message)
    if not match:
        return None

    filename = match.group(1).strip()
    ip_int = int(match.group(2))
    port = int(match.group(3))
    filesize = int(match.group(4))

    # Convert integer IP to dotted quad
    ip = socket.inet_ntoa(struct.pack(">I", ip_int))

    return DCCSendOffer(
        filename=filename,
        ip=ip,
        port=port,
        filesize=filesize,
    )


class DCCTransferError(Exception):
    """Raised when a DCC transfer fails."""
    pass


class DCCTimeoutError(DCCTransferError):
    """Raised when a DCC transfer exceeds the total timeout."""
    pass


def receive_dcc_file(
    offer: DCCSendOffer,
    save_path: Path,
    progress_callback=None,
    proxy: Optional[tuple[str, int]] = None,
) -> Path:
    """Download a file via DCC SEND.
    
    Opens a raw TCP connection to the sender and reads exactly `filesize` bytes.
    The DCC protocol on irchighway does NOT send EOF, so we must track bytes.
    
    Includes:
      - Connect timeout (30s)
      - Per-read timeout (60s) 
      - Overall transfer timeout (300s for books, 60s for search results)
      - Optional SOCKS5 proxy support
    
    Args:
        offer: Parsed DCC SEND offer
        save_path: Directory to save the file in
        progress_callback: Optional callable(bytes_received, total_bytes)
        proxy: Optional (ip, port) tuple for SOCKS5 proxy
    
    Returns:
        Path to the saved file
    
    Raises:
        DCCTransferError: on connection or transfer failure
        DCCTimeoutError: if total timeout exceeded
    """
    filepath = save_path / offer.filename
    
    # Avoid overwriting - add suffix if exists
    counter = 1
    original = filepath
    while filepath.exists():
        filepath = original.with_stem(f"{original.stem}_{counter}")
        counter += 1

    total_timeout = DCC_SEARCH_TOTAL_TIMEOUT if offer.is_search_result else DCC_TOTAL_TIMEOUT
    start_time = time.monotonic()
    received = 0
    chunk_size = 8192

    # Create socket - proxied or direct
    if proxy:
        sock = socks.socksocket(socket.AF_INET, socket.SOCK_STREAM)
        sock.set_proxy(socks.SOCKS5, proxy[0], proxy[1])
        logger.info(f"DCC connecting to {offer.ip}:{offer.port} via proxy {proxy[0]}:{proxy[1]}")
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logger.info(f"DCC connecting to {offer.ip}:{offer.port} for {offer.filename}")

    sock.settimeout(DCC_CONNECT_TIMEOUT)

    try:
        try:
            sock.connect((offer.ip, offer.port))
        except socket.timeout:
            raise DCCTransferError(f"Connection timed out to {offer.ip}:{offer.port}")
        except ConnectionRefusedError:
            raise DCCTransferError(f"Connection refused by {offer.ip}:{offer.port}")
        except socks.ProxyConnectionError as e:
            raise DCCTransferError(f"Proxy connection failed for {offer.ip}:{offer.port}: {e}")
        except OSError as e:
            raise DCCTransferError(f"Connection failed to {offer.ip}:{offer.port}: {e}")

        # Switch to read timeout after connecting
        sock.settimeout(DCC_READ_TIMEOUT)

        with open(filepath, "wb") as f:
            while received < offer.filesize:
                # Check overall timeout
                elapsed = time.monotonic() - start_time
                if elapsed > total_timeout:
                    raise DCCTimeoutError(
                        f"Transfer timed out after {elapsed:.0f}s "
                        f"({received}/{offer.filesize} bytes received)"
                    )

                remaining = offer.filesize - received
                to_read = min(chunk_size, remaining)
                
                try:
                    data = sock.recv(to_read)
                except socket.timeout:
                    raise DCCTransferError(
                        f"Read timed out after {DCC_READ_TIMEOUT}s "
                        f"({received}/{offer.filesize} bytes received)"
                    )

                if not data:
                    # Connection closed prematurely
                    logger.warning(
                        f"DCC connection closed early: {received}/{offer.filesize} bytes "
                        f"for {offer.filename}"
                    )
                    break
                
                f.write(data)
                received += len(data)

                if progress_callback:
                    progress_callback(received, offer.filesize)

    except (DCCTransferError, DCCTimeoutError):
        # Clean up partial file on timeout/error
        if filepath.exists() and received == 0:
            try:
                filepath.unlink()
            except Exception:
                pass
        raise
    finally:
        sock.close()

    elapsed = time.monotonic() - start_time
    if received < offer.filesize:
        logger.warning(
            f"DCC partial download: {received}/{offer.filesize} bytes "
            f"in {elapsed:.1f}s for {offer.filename}"
        )
    else:
        logger.info(
            f"DCC complete: {received} bytes in {elapsed:.1f}s for {offer.filename}"
        )

    return filepath


def extract_search_results(filepath: Path) -> str:
    """Extract search results text from a file.
    
    Handles both plain .txt and .txt.zip compressed results.
    Returns the text content.
    """
    if filepath.suffix == ".zip" or str(filepath).endswith(".txt.zip"):
        with zipfile.ZipFile(filepath, "r") as zf:
            # Get the first text file in the archive
            for name in zf.namelist():
                if name.endswith(".txt"):
                    return zf.read(name).decode("utf-8", errors="replace")
            # If no .txt found, just read the first file
            if zf.namelist():
                return zf.read(zf.namelist()[0]).decode("utf-8", errors="replace")
        return ""
    else:
        return filepath.read_text(encoding="utf-8", errors="replace")


@dataclass
class SearchResult:
    """A single book entry from search results."""
    bot_name: str
    full_command: str  # The full "!botname filename" command to send
    display_name: str  # Human-readable name
    file_format: str
    file_size: str

    def to_dict(self):
        return {
            "bot_name": self.bot_name,
            "full_command": self.full_command,
            "display_name": self.display_name,
            "file_format": self.file_format,
            "file_size": self.file_size,
        }


# Regex to parse result lines like: !BotName Author - Title.epub ::INFO:: 1.2MB
RESULT_LINE_RE = re.compile(
    r'^(!\S+)\s+(.+?)\s+::INFO::\s*(.*)$'
)


def parse_search_results(text: str) -> list[SearchResult]:
    """Parse search results text into a list of SearchResult objects.
    
    Each line starting with ! is a downloadable book entry.
    Format: !<botname> <content> ::INFO:: <size>
    """
    results = []

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("!"):
            continue

        match = RESULT_LINE_RE.match(line)
        if not match:
            continue

        bot_name = match.group(1)
        content = match.group(2).strip()
        size_info = match.group(3).strip()

        # Extract file format from the content
        fmt = "unknown"
        for ext in (".epub", ".mobi", ".pdf", ".azw3", ".txt", ".djvu", ".cbr", ".cbz", ".doc", ".rtf"):
            if ext in content.lower():
                fmt = ext.lstrip(".")
                break

        # The full command to download is: "!botname content"
        # which is basically the original line minus ::INFO:: part
        full_command = f"{bot_name} {content}"

        results.append(SearchResult(
            bot_name=bot_name,
            full_command=full_command,
            display_name=content,
            file_format=fmt,
            file_size=size_info,
        ))

    return results
