import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_client_ip, require_auth
from app.database import get_db
from app.irc_bot import bot, DownloadJob
from app.models import Book, Download

router = APIRouter(prefix="/api", tags=["books"])
logger = logging.getLogger("ircbot.routes.books")


class DownloadRequest(BaseModel):
    command: str  # e.g. "!BotName Author - Title.epub"


@router.post("/download", dependencies=[Depends(require_auth)])
async def request_download(req: DownloadRequest, db: AsyncSession = Depends(get_db)):
    """Request a book download from IRC."""
    command = req.command.strip()
    if not command.startswith("!"):
        raise HTTPException(status_code=400, detail="Command must start with !")

    if not bot.is_connected:
        raise HTTPException(status_code=503, detail="IRC bot is not connected")

    # Check if we already have this book
    result = await db.execute(select(Book).where(Book.irc_command == command))
    existing = result.scalar_one_or_none()
    if existing:
        return {
            "status": "already_exists",
            "book": existing.to_dict(),
            "message": "Book already downloaded",
        }

    # Submit to IRC bot
    bot.submit_download(DownloadJob(book_command=command))

    return {
        "status": "requested",
        "command": command,
        "message": "Download requested, check library for completion",
    }


@router.get("/books", dependencies=[Depends(require_auth)])
async def list_books(
    q: str = "",
    format: str = "",
    db: AsyncSession = Depends(get_db),
):
    """List all downloaded books with optional filtering."""
    query = select(Book).order_by(Book.created_at.desc())

    if q:
        query = query.where(
            Book.title.ilike(f"%{q}%") | Book.author.ilike(f"%{q}%")
        )

    if format:
        query = query.where(Book.format == format)

    result = await db.execute(query)
    books = result.scalars().all()
    return [b.to_dict() for b in books]


@router.get("/books/{book_id}", dependencies=[Depends(require_auth)])
async def get_book(book_id: int, db: AsyncSession = Depends(get_db)):
    """Get book details."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book.to_dict()


@router.get("/books/{book_id}/download", dependencies=[Depends(require_auth)])
async def download_book(
    book_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Download a book file. Logs IP address."""
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    from pathlib import Path
    filepath = Path(book.file_path)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Log the download with IP
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")

    download_record = Download(
        book_id=book.id,
        ip_address=ip,
        user_agent=user_agent,
    )
    db.add(download_record)
    await db.flush()

    logger.info(f"Book download: {book.title} by IP {ip}")

    return FileResponse(
        path=filepath,
        filename=book.filename,
        media_type="application/octet-stream",
    )
