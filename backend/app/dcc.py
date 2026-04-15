"""DCC SEND parser and raw TCP file receiver.

Handles the low-level protocol for receiving files over DCC from IRC bots.
irchighway DCC quirks:
  - No EOF: server does NOT close connection, must track bytes vs declared size
  - Integer IP: sent as big-endian 32-bit unsigned int
  - Filename quoting: may or may not be wrapped in double quotes
  - Search results may be .txt.zip compressed
"""

import io
import re
import socket
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Regex for DCC SEND: handles both quoted and unquoted filenames
DCC_SEND_RE = re.compile(
    r'DCC SEND "?(.+?)"?\s+(\d+)\s+(\d+)\s+(\d+)'
)


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


def receive_dcc_file(offer: DCCSendOffer, save_path: Path, progress_callback=None) -> Path:
    """Download a file via DCC SEND.
    
    Opens a raw TCP connection to the sender and reads exactly `filesize` bytes.
    The DCC protocol on irchighway does NOT send EOF, so we must track bytes.
    
    Args:
        offer: Parsed DCC SEND offer
        save_path: Directory to save the file in
        progress_callback: Optional callable(bytes_received, total_bytes)
    
    Returns:
        Path to the saved file
    """
    filepath = save_path / offer.filename
    
    # Avoid overwriting - add suffix if exists
    counter = 1
    original = filepath
    while filepath.exists():
        filepath = original.with_stem(f"{original.stem}_{counter}")
        counter += 1

    received = 0
    chunk_size = 8192

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(60)  # 60 second timeout per read

    try:
        sock.connect((offer.ip, offer.port))

        with open(filepath, "wb") as f:
            while received < offer.filesize:
                remaining = offer.filesize - received
                to_read = min(chunk_size, remaining)
                
                data = sock.recv(to_read)
                if not data:
                    # Connection closed prematurely
                    break
                
                f.write(data)
                received += len(data)

                if progress_callback:
                    progress_callback(received, offer.filesize)
    finally:
        sock.close()

    if received < offer.filesize:
        # Partial download - keep it but log
        pass

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
