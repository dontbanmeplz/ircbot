import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.auth import require_admin
from app.database import get_db
from app.models import Download, IPTag, SearchPreferences

router = APIRouter(prefix="/api/admin", tags=["admin"])
logger = logging.getLogger("ircbot.routes.admin")


@router.get("/downloads", dependencies=[Depends(require_admin)])
async def list_downloads(
    ip: str = "",
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List download activity with IP tracking info."""
    query = (
        select(Download)
        .options(joinedload(Download.book))
        .order_by(Download.downloaded_at.desc())
        .limit(limit)
        .offset(offset)
    )

    if ip:
        query = query.where(Download.ip_address == ip)

    result = await db.execute(query)
    downloads = result.scalars().unique().all()

    # Get all IP tags for quick lookup
    tag_result = await db.execute(select(IPTag))
    tags = {t.ip_address: t.to_dict() for t in tag_result.scalars().all()}

    return [
        {
            **d.to_dict(),
            "ip_tag": tags.get(d.ip_address),
        }
        for d in downloads
    ]


@router.get("/downloads/stats", dependencies=[Depends(require_admin)])
async def download_stats(db: AsyncSession = Depends(get_db)):
    """Get download statistics grouped by IP."""
    result = await db.execute(
        select(
            Download.ip_address,
            func.count(Download.id).label("download_count"),
            func.max(Download.downloaded_at).label("last_download"),
        )
        .group_by(Download.ip_address)
        .order_by(func.count(Download.id).desc())
    )
    rows = result.all()

    # Get all IP tags
    tag_result = await db.execute(select(IPTag))
    tags = {t.ip_address: t.to_dict() for t in tag_result.scalars().all()}

    return [
        {
            "ip_address": row.ip_address,
            "download_count": row.download_count,
            "last_download": row.last_download.isoformat() if row.last_download else None,
            "ip_tag": tags.get(row.ip_address),
        }
        for row in rows
    ]


class IPTagCreate(BaseModel):
    ip_address: str
    tag_name: str
    notes: Optional[str] = None


class IPTagUpdate(BaseModel):
    tag_name: Optional[str] = None
    notes: Optional[str] = None


@router.get("/ip-tags", dependencies=[Depends(require_admin)])
async def list_ip_tags(db: AsyncSession = Depends(get_db)):
    """List all IP tags."""
    result = await db.execute(select(IPTag).order_by(IPTag.created_at.desc()))
    return [t.to_dict() for t in result.scalars().all()]


@router.post("/ip-tags", dependencies=[Depends(require_admin)])
async def create_ip_tag(req: IPTagCreate, db: AsyncSession = Depends(get_db)):
    """Tag an IP address with a friendly name."""
    # Check if tag already exists for this IP
    result = await db.execute(select(IPTag).where(IPTag.ip_address == req.ip_address))
    existing = result.scalar_one_or_none()

    if existing:
        existing.tag_name = req.tag_name
        if req.notes is not None:
            existing.notes = req.notes
        await db.flush()
        return existing.to_dict()

    tag = IPTag(
        ip_address=req.ip_address,
        tag_name=req.tag_name,
        notes=req.notes,
    )
    db.add(tag)
    await db.flush()
    await db.refresh(tag)

    logger.info(f"Tagged IP {req.ip_address} as '{req.tag_name}'")
    return tag.to_dict()


@router.put("/ip-tags/{tag_id}", dependencies=[Depends(require_admin)])
async def update_ip_tag(tag_id: int, req: IPTagUpdate, db: AsyncSession = Depends(get_db)):
    """Update an IP tag."""
    result = await db.execute(select(IPTag).where(IPTag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    if req.tag_name is not None:
        tag.tag_name = req.tag_name
    if req.notes is not None:
        tag.notes = req.notes

    await db.flush()
    return tag.to_dict()


@router.delete("/ip-tags/{tag_id}", dependencies=[Depends(require_admin)])
async def delete_ip_tag(tag_id: int, db: AsyncSession = Depends(get_db)):
    """Delete an IP tag."""
    result = await db.execute(select(IPTag).where(IPTag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    await db.delete(tag)
    await db.flush()
    return {"deleted": True}


# --- Search Preferences ---

class WeightRule(BaseModel):
    tag: str           # Category: "provider", "quality", "language", etc.
    pattern: str       # Substring to match against bot name + display name
    weight: int        # Higher = shown first, negative = pushed down
    label: str         # Human-readable description


class SearchPrefsUpdate(BaseModel):
    allowed_formats: list[str]
    weight_rules: list[WeightRule]


async def _get_or_create_prefs(db: AsyncSession) -> SearchPreferences:
    """Get the singleton search preferences row, creating defaults if missing."""
    result = await db.execute(select(SearchPreferences))
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = SearchPreferences(
            allowed_formats='["epub"]',
            weight_rules='[]',
        )
        db.add(prefs)
        await db.flush()
        await db.refresh(prefs)
    return prefs


@router.get("/search-prefs", dependencies=[Depends(require_admin)])
async def get_search_prefs(db: AsyncSession = Depends(get_db)):
    """Get current search result preferences."""
    prefs = await _get_or_create_prefs(db)
    return prefs.to_dict()


@router.put("/search-prefs", dependencies=[Depends(require_admin)])
async def update_search_prefs(req: SearchPrefsUpdate, db: AsyncSession = Depends(get_db)):
    """Update search result preferences."""
    import json

    prefs = await _get_or_create_prefs(db)
    prefs.allowed_formats = json.dumps(req.allowed_formats)
    prefs.weight_rules = json.dumps([r.model_dump() for r in req.weight_rules])
    await db.flush()
    await db.refresh(prefs)

    logger.info(f"Search prefs updated: formats={req.allowed_formats}, rules={len(req.weight_rules)}")
    return prefs.to_dict()
