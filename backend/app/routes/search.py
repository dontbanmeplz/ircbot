import asyncio
import json
import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_auth
from app.database import get_db
from app.irc_bot import bot, SearchJob, SearchComplete
from app.models import SearchSession, SearchPreferences

router = APIRouter(prefix="/api", tags=["search"])
logger = logging.getLogger("ircbot.routes.search")


class SearchRequest(BaseModel):
    query: str


async def _load_prefs(db: AsyncSession) -> dict:
    """Load search preferences (formats + weight rules)."""
    result = await db.execute(select(SearchPreferences))
    prefs = result.scalar_one_or_none()
    if prefs:
        return prefs.to_dict()
    # Defaults: epub only, no weight rules
    return {"allowed_formats": ["epub"], "weight_rules": []}


def _apply_prefs(results: list[dict], prefs: dict) -> list[dict]:
    """Filter by allowed formats and sort by weight rules.
    
    Results are dicts with keys: bot_name, full_command, display_name, file_format, file_size.
    Weight rules have: tag, pattern, weight, label.
    """
    allowed = [f.lower() for f in prefs.get("allowed_formats", [])]
    rules = prefs.get("weight_rules", [])

    # Filter formats (if allowed list is empty, show all)
    if allowed:
        results = [r for r in results if r.get("file_format", "").lower() in allowed]

    # Compute weight score for each result
    def score(r: dict) -> int:
        total = 0
        # Match against bot_name + display_name combined
        text = f"{r.get('bot_name', '')} {r.get('display_name', '')}".lower()
        for rule in rules:
            pattern = rule.get("pattern", "").lower()
            if pattern and pattern in text:
                total += rule.get("weight", 0)
        return total

    # Sort by weight descending (highest first), stable sort preserves original order for ties
    results.sort(key=lambda r: score(r), reverse=True)

    return results


@router.post("/search", dependencies=[Depends(require_auth)])
async def start_search(req: SearchRequest, db: AsyncSession = Depends(get_db)):
    """Start a book search. Returns a session ID to poll for results."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if not bot.is_connected:
        raise HTTPException(status_code=503, detail="IRC bot is not connected")

    # Create search session in DB
    session = SearchSession(query=req.query.strip(), status="pending")
    db.add(session)
    await db.flush()
    await db.refresh(session)

    # Submit to IRC bot
    bot.submit_search(SearchJob(session_id=session.id, query=req.query.strip()))

    # Update status
    session.status = "searching"
    await db.flush()

    return {"id": session.id, "status": "searching", "query": req.query.strip()}


@router.get("/search/{session_id}", dependencies=[Depends(require_auth)])
async def get_search_status(session_id: int, db: AsyncSession = Depends(get_db)):
    """Poll search status and results. Results are filtered/weighted by admin prefs."""
    result = await db.execute(select(SearchSession).where(SearchSession.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Search session not found")

    await db.refresh(session)

    data = session.to_dict()

    # Apply search preferences to completed results
    if session.status == "complete" and data["results"]:
        prefs = await _load_prefs(db)
        filtered = _apply_prefs(data["results"], prefs)
        data["results"] = filtered
        data["result_count"] = len(filtered)

    return data


@router.get("/searches", dependencies=[Depends(require_auth)])
async def list_searches(db: AsyncSession = Depends(get_db)):
    """List recent search sessions."""
    result = await db.execute(
        select(SearchSession).order_by(SearchSession.created_at.desc()).limit(20)
    )
    sessions = result.scalars().all()
    return [s.to_dict() for s in sessions]
