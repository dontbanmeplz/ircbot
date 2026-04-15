"""FastAPI application - main entrypoint.

Starts the IRC bot in a background thread, runs a poller to sync bot results
back to the database, and serves the API + static frontend.
"""

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from queue import Empty

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.auth import require_auth
from app.config import settings
from app.database import async_session, init_db
from app.irc_bot import bot, DownloadComplete, SearchComplete
from app.models import Book, SearchSession
from app.routes import auth, search, books, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("ircbot")


async def _poll_bot_results():
    """Background task: drain bot result queues into the database.
    
    The IRC bot runs in a separate thread and pushes results into
    thread-safe queues. This coroutine runs in the async event loop
    and periodically checks those queues, writing results to the DB.
    """
    while True:
        try:
            # Process search results
            while True:
                try:
                    result: SearchComplete = bot.search_results.get_nowait()
                    await _handle_search_complete(result)
                except Empty:
                    break

            # Process download results
            while True:
                try:
                    result: DownloadComplete = bot.download_results.get_nowait()
                    await _handle_download_complete(result)
                except Empty:
                    break

        except Exception as e:
            logger.error(f"Error in bot result poller: {e}", exc_info=True)

        await asyncio.sleep(0.5)


async def _handle_search_complete(result: SearchComplete):
    """Write completed search results to the database."""
    async with async_session() as db:
        from sqlalchemy import select
        stmt = select(SearchSession).where(SearchSession.id == result.session_id)
        row = await db.execute(stmt)
        session = row.scalar_one_or_none()

        if not session:
            logger.warning(f"Search session {result.session_id} not found in DB")
            return

        if result.error:
            session.status = "failed"
            session.error_message = result.error
        else:
            session.status = "complete"
            session.results_json = json.dumps(result.results)

        await db.commit()
        logger.info(
            f"Search session {result.session_id}: {session.status} "
            f"({len(result.results)} results)"
        )


async def _handle_download_complete(result: DownloadComplete):
    """Write completed book download to the database."""
    async with async_session() as db:
        if result.error:
            logger.error(f"Download failed for '{result.book_command}': {result.error}")
            return

        if not result.filepath or not result.filepath.exists():
            logger.error(f"Download file missing for '{result.book_command}'")
            return

        # Parse author/title from the command
        # Format: "!BotName Author - Title.format"
        title = result.filename or result.filepath.name
        author = "Unknown"
        source_bot = None

        cmd = result.book_command
        if cmd.startswith("!"):
            parts = cmd.split(" ", 1)
            source_bot = parts[0]
            if len(parts) > 1:
                content = parts[1]
                # Try to split "Author - Title.ext"
                if " - " in content:
                    author_part, title_part = content.split(" - ", 1)
                    author = author_part.strip()
                    title = title_part.strip()
                else:
                    title = content.strip()

        # Detect format
        fmt = "unknown"
        suffix = result.filepath.suffix.lower().lstrip(".")
        if suffix in ("epub", "mobi", "pdf", "azw3", "txt", "djvu", "cbr", "cbz", "doc", "rtf"):
            fmt = suffix

        book = Book(
            title=title,
            author=author,
            filename=result.filename or result.filepath.name,
            file_path=str(result.filepath),
            file_size=result.filesize,
            format=fmt,
            source_bot=source_bot,
            irc_command=result.book_command,
        )
        db.add(book)
        await db.commit()
        logger.info(f"Book saved: '{title}' by {author} ({fmt}, {result.filesize} bytes)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: start DB + IRC bot on startup, stop on shutdown."""
    # Startup
    await init_db()
    logger.info("Database initialized")

    bot.start()
    logger.info("IRC bot starting...")

    # Start the background poller
    poller_task = asyncio.create_task(_poll_bot_results())

    yield

    # Shutdown
    poller_task.cancel()
    bot.stop()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="IRC Book Bot",
    description="Search and download books from IRC with a web interface",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for local dev (React dev server on different port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(auth.router)
app.include_router(search.router)
app.include_router(books.router)
app.include_router(admin.router)


@app.get("/api/status", dependencies=[Depends(require_auth)])
async def get_status():
    """Get IRC bot connection status."""
    return bot.status


# Serve the React frontend in production (static files)
frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
