"""
Creator Discovery Engine — API Routes

All endpoints for the creator management platform.
"""

from uuid import UUID
from typing import Optional
from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, desc, asc, delete

from app.core.database import get_db
from app.models.models import (
    Creator, CreatorTag, CreatorNote, DiscoverySearch, DiscoveryResult,
    OutreachEmail, EmailTemplate, OutreachStatus,
)
from app.models.schemas import (
    CreatorCreate, CreatorUpdate, CreatorResponse, CreatorListResponse,
    CreatorFilter, DiscoverySearchRequest, DiscoverySearchResponse,
    DiscoveryResultResponse, OutreachEmailCreate, OutreachEmailResponse,
    EmailTemplateCreate, EmailTemplateResponse, ImportResult,
)
from app.services.discovery_engine import (
    DiscoveryEngine, parse_search_intent, analyze_results, deduplicate_results,
)
from app.services.import_service import import_spreadsheet
from app.services.clickup_service import ClickUpService

router = APIRouter()
logger = logging.getLogger(__name__)


async def _background_enrich(creator_id: UUID):
    """Shared background enrichment task — handles its own DB session and eager loading."""
    from app.core.database import async_session_factory
    from app.services.enrichment_service import enrich_creator, _update_status
    from sqlalchemy.orm import selectinload

    async with async_session_factory() as session:
        result = await session.execute(
            select(Creator).where(Creator.id == creator_id).options(selectinload(Creator.notes))
        )
        creator_obj = result.scalar_one_or_none()
        if not creator_obj:
            return
        try:
            await enrich_creator(creator_obj, session)
        except Exception as e:
            _update_status(str(creator_id),
                status="failed",
                error=str(e),
                step_label=f"Failed: {str(e)[:100]}",
            )
            logger.error(f"Enrichment failed for {creator_id}: {e}")


# ─── CREATOR CRUD ───

@router.get("/creators", response_model=CreatorListResponse)
async def list_creators(
    search: Optional[str] = None,
    pipeline_stage: Optional[str] = None,
    quality_tier: Optional[str] = None,
    source: Optional[str] = None,
    platform: Optional[str] = None,
    categories: Optional[str] = None,  # comma-separated
    has_email: Optional[bool] = None,
    is_core_team: Optional[bool] = None,
    follower_min: Optional[int] = None,
    follower_max: Optional[int] = None,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    page: int = 1,
    per_page: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List and filter creators."""
    query = select(Creator)

    # Text search across name, email, handle, categories, notes
    if search:
        search_term = f"%{search}%"
        query = query.where(
            or_(
                Creator.name.ilike(search_term),
                Creator.email.ilike(search_term),
                Creator.tiktok_handle.ilike(search_term),
                Creator.instagram_handle.ilike(search_term),
                Creator.content_notes.ilike(search_term),
                Creator.bio.ilike(search_term),
                Creator.city.ilike(search_term),
                Creator.state.ilike(search_term),
            )
        )

    # Enum filters
    if pipeline_stage:
        query = query.where(Creator.pipeline_stage == pipeline_stage)
    if quality_tier:
        query = query.where(Creator.quality_tier == quality_tier)
    if source:
        query = query.where(Creator.source == source)
    if is_core_team is not None:
        query = query.where(Creator.is_core_team == is_core_team)
    if has_email is not None:
        if has_email:
            query = query.where(Creator.email.isnot(None))
        else:
            query = query.where(Creator.email.is_(None))

    # Platform presence filter
    if platform:
        platform_map = {
            "tiktok": Creator.tiktok_url.isnot(None),
            "instagram": Creator.instagram_url.isnot(None),
            "youtube": Creator.youtube_url.isnot(None),
            "twitter": Creator.twitter_url.isnot(None),
            "facebook": Creator.facebook_url.isnot(None),
        }
        if platform in platform_map:
            query = query.where(platform_map[platform])

    # Category filter (JSONB contains)
    if categories:
        cat_list = [c.strip() for c in categories.split(",")]
        for cat in cat_list:
            query = query.where(Creator.categories.contains([cat]))

    # Follower range
    if follower_min:
        query = query.where(Creator.total_followers >= follower_min)
    if follower_max:
        query = query.where(Creator.total_followers <= follower_max)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Sort
    sort_col = getattr(Creator, sort_by, Creator.created_at)
    query = query.order_by(desc(sort_col) if sort_dir == "desc" else asc(sort_col))

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    creators = result.scalars().all()

    return CreatorListResponse(
        creators=[CreatorResponse.model_validate(c) for c in creators],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/creators/{creator_id}", response_model=CreatorResponse)
async def get_creator(creator_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single creator by ID."""
    creator = await db.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    return CreatorResponse.model_validate(creator)


@router.post("/creators", response_model=CreatorResponse)
async def create_creator(data: CreatorCreate, db: AsyncSession = Depends(get_db)):
    """Manually create a creator."""
    # Check for duplicate email
    if data.email:
        existing = await db.execute(
            select(Creator).where(Creator.email == data.email)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Creator with this email already exists")

    creator = Creator(**data.model_dump())
    db.add(creator)
    await db.commit()
    await db.refresh(creator)
    return CreatorResponse.model_validate(creator)


@router.patch("/creators/{creator_id}", response_model=CreatorResponse)
async def update_creator(creator_id: UUID, data: CreatorUpdate, db: AsyncSession = Depends(get_db)):
    """Update a creator."""
    creator = await db.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(creator, field, value)

    await db.commit()
    await db.refresh(creator)
    return CreatorResponse.model_validate(creator)


@router.delete("/creators/{creator_id}")
async def delete_creator(creator_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete a creator."""
    creator = await db.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    await db.delete(creator)
    await db.commit()
    return {"deleted": True}


@router.delete("/creators/bulk/all")
async def delete_all_creators(confirm: str = "no", db: AsyncSession = Depends(get_db)):
    """Delete ALL creators. Requires confirm=yes query parameter."""
    if confirm != "yes":
        return {"error": "Pass ?confirm=yes to delete all creators"}
    result = await db.execute(select(func.count(Creator.id)))
    count = result.scalar() or 0
    await db.execute(delete(Creator))
    await db.commit()
    return {"deleted": count, "message": f"Deleted {count} creators"}


@router.delete("/creators/bulk/discovered")
async def delete_discovered_creators(db: AsyncSession = Depends(get_db)):
    """Delete all creators with pipeline_stage='discovered' (test/unvetted data)."""
    result = await db.execute(
        select(func.count(Creator.id)).where(Creator.pipeline_stage == "discovered")
    )
    count = result.scalar() or 0
    await db.execute(
        delete(Creator).where(Creator.pipeline_stage == "discovered")
    )
    await db.commit()
    return {"deleted": count, "message": f"Deleted {count} discovered creators"}


# ─── IMPORT ───

@router.post("/import", response_model=ImportResult)
async def import_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Import creators from a CSV or Excel file."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed = (".csv", ".xlsx", ".xls")
    if not any(file.filename.lower().endswith(ext) for ext in allowed):
        raise HTTPException(status_code=400, detail=f"Unsupported format. Use: {', '.join(allowed)}")

    content = await file.read()
    result = await import_spreadsheet(content, file.filename, db)
    return result


# ─── DISCOVERY ───

@router.post("/discover")
async def discover_creators(
    request: DiscoverySearchRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Start an AI-powered creator discovery search.
    Returns immediately with a search_id. Poll GET /discover/{search_id} for results.
    """
    import asyncio

    engine = DiscoveryEngine()

    filters = {}
    if request.follower_min:
        filters["follower_min"] = request.follower_min
    if request.follower_max:
        filters["follower_max"] = request.follower_max
    if request.engagement_min:
        filters["engagement_min"] = request.engagement_min
    if request.categories:
        filters["categories"] = request.categories

    # Create search record immediately so we have an ID to return
    search = DiscoverySearch(
        query=request.query,
        platforms_searched=request.platforms,
        filters=filters,
        status="starting",
    )
    db.add(search)
    await db.commit()
    await db.refresh(search)
    search_id = search.id

    # Capture request values before the endpoint returns (request obj may be GC'd)
    query_text = str(request.query)
    platforms_list = list(request.platforms)
    max_results_val = int(request.max_results)

    # Run discovery in background
    async def _run_discovery():
        from app.core.database import async_session_factory
        try:
            async with async_session_factory() as session:
                try:
                    eng = DiscoveryEngine()
                    s = await session.get(DiscoverySearch, search_id)
                    if not s:
                        logger.error(f"[Discovery] Search record {search_id} not found")
                        return

                    s.status = "parsing_intent"
                    await session.commit()

                    # Step 1: Parse intent
                    logger.info(f"[Discovery] Parsing intent: {query_text}")
                    intent = await parse_search_intent(query_text, platforms_list)
                    s.parsed_intent = intent
                    s.status = "searching"
                    await session.commit()

                    # Step 2: Fan out searches
                    logger.info(f"[Discovery] Running searches...")
                    search_tasks = []

                    web_queries = intent.get("search_queries", [])
                    if web_queries:
                        search_tasks.append(eng.web_search.search(web_queries))

                    subreddits = intent.get("subreddits", [])
                    if subreddits:
                        reddit_terms = intent.get("topics", [query_text])
                        search_tasks.append(eng.reddit_search.search(subreddits, reddit_terms))

                    ugc_terms = intent.get("ugc_search_terms", [])
                    if ugc_terms:
                        search_tasks.append(eng.ugc_search.search(ugc_terms))

                    hashtags = intent.get("hashtags", [])
                    if hashtags:
                        search_tasks.append(eng.hashtag_search.search(hashtags, platforms_list))

                    raw_results_groups = await asyncio.gather(*search_tasks, return_exceptions=True)

                    raw_results = []
                    for group in raw_results_groups:
                        if isinstance(group, list):
                            raw_results.extend(group)
                        elif isinstance(group, Exception):
                            logger.error(f"Search task failed: {group}")

                    logger.info(f"[Discovery] Got {len(raw_results)} raw results")
                    s.status = "analyzing"
                    await session.commit()

                    # Step 3: AI Analysis
                    analyzed = await analyze_results(raw_results, intent, query_text)
                    logger.info(f"[Discovery] AI analyzed {len(analyzed)} results")

                    # Step 4: Deduplicate
                    unique = deduplicate_results(analyzed)
                    unique.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
                    final = unique[:max_results_val]

                    # Step 5: Store results
                    for rd in final:
                        result = DiscoveryResult(
                            search_id=search_id,
                            name=rd.get("name", "Unknown"),
                            handle=rd.get("handle"),
                            platform=rd.get("platform", "unknown"),
                            profile_url=rd.get("profile_url"),
                            bio=rd.get("bio"),
                            email=rd.get("email"),
                            followers=rd.get("estimated_followers"),
                            engagement_rate=rd.get("estimated_engagement_rate"),
                            relevance_score=rd.get("relevance_score"),
                            categories=rd.get("categories", []),
                            ai_analysis={
                                "credentials": rd.get("credentials", []),
                                "content_fit": rd.get("content_fit_reasoning"),
                                "red_flags": rd.get("red_flags", []),
                                "recommended_action": rd.get("recommended_action"),
                                "other_profiles": rd.get("other_profiles", {}),
                                "past_partnerships": rd.get("past_partnerships", []),
                            },
                            source_type=rd.get("source", "web_search"),
                            source_url=rd.get("source_urls", [None])[0] if rd.get("source_urls") else None,
                            raw_data=rd,
                        )
                        session.add(result)

                    s.results_count = len(final)
                    s.status = "complete"
                    s.completed_at = datetime.utcnow()
                    await session.commit()
                    logger.info(f"[Discovery] Complete: {len(final)} results")

                except Exception as e:
                    logger.error(f"[Discovery] Search failed: {e}", exc_info=True)
                    try:
                        s = await session.get(DiscoverySearch, search_id)
                        if s:
                            s.status = "failed"
                            s.error = str(e)[:500]
                            await session.commit()
                    except Exception as e2:
                        logger.error(f"[Discovery] Failed to update search status: {e2}")

        except Exception as outer_e:
            logger.error(f"[Discovery] Background task crashed: {outer_e}", exc_info=True)

    asyncio.create_task(_run_discovery())

    return {
        "search_id": str(search_id),
        "query": request.query,
        "status": "starting",
        "message": "Search started. Poll GET /discover/{search_id} for results.",
    }


@router.get("/discover/history")
async def discovery_history(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get recent discovery search history."""
    result = await db.execute(
        select(DiscoverySearch)
        .order_by(desc(DiscoverySearch.started_at))
        .limit(limit)
    )
    searches = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "query": s.query,
            "status": s.status,
            "results_count": s.results_count,
            "results_saved": s.results_saved,
            "started_at": s.started_at.isoformat(),
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        }
        for s in searches
    ]


@router.get("/discover/{search_id}")
async def get_discovery_results(search_id: UUID, db: AsyncSession = Depends(get_db)):
    """Poll for discovery search results. Returns status + results when complete."""
    search = await db.get(DiscoverySearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    response = {
        "search_id": str(search.id),
        "query": search.query,
        "status": search.status,
        "parsed_intent": search.parsed_intent,
        "platforms_searched": search.platforms_searched or [],
        "results_count": search.results_count or 0,
        "started_at": search.started_at.isoformat() if search.started_at else None,
        "completed_at": search.completed_at.isoformat() if search.completed_at else None,
        "results": [],
    }

    # Only load results if complete
    if search.status == "complete":
        result = await db.execute(
            select(DiscoveryResult)
            .where(DiscoveryResult.search_id == search.id)
            .order_by(desc(DiscoveryResult.relevance_score))
        )
        results = result.scalars().all()
        response["results"] = [DiscoveryResultResponse.model_validate(r).__dict__ for r in results]

    return response


@router.post("/discover/results/{result_id}/save", response_model=CreatorResponse)
async def save_discovery_result(result_id: UUID, db: AsyncSession = Depends(get_db)):
    """Save a discovery result as a creator in the database."""
    engine = DiscoveryEngine()
    creator = await engine.save_result_as_creator(result_id, db)
    return CreatorResponse.model_validate(creator)


@router.post("/discover/results/{result_id}/save-and-enrich")
async def save_and_enrich_discovery_result(result_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Save a discovery result as a creator AND immediately start enrichment.
    """
    import asyncio
    from app.services.enrichment_service import enrich_creator, _update_status

    engine = DiscoveryEngine()
    creator = await engine.save_result_as_creator(result_id, db)
    creator_id = creator.id

    # Kick off enrichment in background
    asyncio.create_task(_background_enrich(creator_id))

    return {
        "creator": CreatorResponse.model_validate(creator).model_dump(),
        "enrichment_status": "started",
        "message": "Creator saved. Enrichment running — poll /creators/{id}/enrich/status for progress.",
    }


@router.post("/discover/{search_id}/save-and-enrich-all")
async def save_and_enrich_all(search_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Save ALL unsaved discovery results from a search and start enrichment on each.
    Returns list of saved creator IDs for polling.
    """
    import asyncio

    search = await db.get(DiscoverySearch, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Search not found")

    # Get all unsaved results
    result = await db.execute(
        select(DiscoveryResult)
        .where(
            DiscoveryResult.search_id == search.id,
            DiscoveryResult.creator_id.is_(None),  # Not yet saved
        )
        .order_by(desc(DiscoveryResult.relevance_score))
    )
    unsaved = result.scalars().all()

    if not unsaved:
        return {"saved": 0, "creators": [], "message": "All results already saved"}

    engine = DiscoveryEngine()
    saved_creators = []

    for dr in unsaved:
        try:
            creator = await engine.save_result_as_creator(dr.id, db)
            saved_creators.append({
                "id": str(creator.id),
                "name": creator.name,
                "discovery_result_id": str(dr.id),
            })
            # Start enrichment in background
            asyncio.create_task(_background_enrich(creator.id))
        except Exception as e:
            logger.warning(f"[Batch] Failed to save result {dr.id}: {e}")
            continue

    return {
        "saved": len(saved_creators),
        "creators": saved_creators,
        "message": f"Saved {len(saved_creators)} creators. Enrichment running on all.",
    }


# ─── OUTREACH ───

@router.post("/outreach", response_model=OutreachEmailResponse)
async def create_outreach(data: OutreachEmailCreate, db: AsyncSession = Depends(get_db)):
    """Create an outreach email (as draft or send immediately)."""
    creator = await db.get(Creator, data.creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")
    if not creator.email:
        raise HTTPException(status_code=400, detail="Creator has no email address")

    outreach = OutreachEmail(
        creator_id=data.creator_id,
        subject=data.subject,
        body=data.body,
        to_email=creator.email,
        status=OutreachStatus.DRAFT,
        template_id=data.template_id,
    )
    db.add(outreach)
    await db.commit()
    await db.refresh(outreach)
    return OutreachEmailResponse.model_validate(outreach)


@router.post("/outreach/{outreach_id}/send")
async def send_outreach(outreach_id: UUID, db: AsyncSession = Depends(get_db)):
    """Send a draft outreach email via Gmail."""
    outreach = await db.get(OutreachEmail, outreach_id)
    if not outreach:
        raise HTTPException(status_code=404, detail="Outreach email not found")

    # TODO: Initialize GmailService with stored OAuth credentials
    # gmail = GmailService.from_tokens(...)
    # success = await gmail.send_email(outreach, db)

    return {"status": "Gmail integration pending — configure OAuth credentials"}


@router.get("/outreach/creator/{creator_id}", response_model=list[OutreachEmailResponse])
async def get_creator_outreach(creator_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get all outreach emails for a creator."""
    result = await db.execute(
        select(OutreachEmail)
        .where(OutreachEmail.creator_id == creator_id)
        .order_by(desc(OutreachEmail.created_at))
    )
    emails = result.scalars().all()
    return [OutreachEmailResponse.model_validate(e) for e in emails]


# ─── EMAIL TEMPLATES ───

@router.get("/templates", response_model=list[EmailTemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    """List all email templates."""
    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.is_active == True)
    )
    templates = result.scalars().all()
    return [EmailTemplateResponse.model_validate(t) for t in templates]


@router.post("/templates", response_model=EmailTemplateResponse)
async def create_template(data: EmailTemplateCreate, db: AsyncSession = Depends(get_db)):
    """Create a new email template."""
    template = EmailTemplate(**data.model_dump())
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return EmailTemplateResponse.model_validate(template)


# ─── CLICKUP SYNC ───

@router.post("/creators/{creator_id}/push-to-clickup")
async def push_to_clickup(creator_id: UUID, db: AsyncSession = Depends(get_db)):
    """Push a creator to ClickUp's Creator Pipeline."""
    creator = await db.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    service = ClickUpService()
    task_id = await service.push_creator(creator, db)

    if task_id:
        return {"success": True, "clickup_task_id": task_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to push to ClickUp")


@router.post("/creators/bulk-push-to-clickup")
async def bulk_push_to_clickup(
    creator_ids: list[UUID],
    db: AsyncSession = Depends(get_db),
):
    """Push multiple creators to ClickUp."""
    creators = []
    for cid in creator_ids:
        creator = await db.get(Creator, cid)
        if creator:
            creators.append(creator)

    service = ClickUpService()
    results = await service.bulk_push(creators, db)
    return results


# ─── NOTES ───

@router.get("/creators/{creator_id}/notes")
async def get_creator_notes(creator_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get activity log / notes for a creator."""
    result = await db.execute(
        select(CreatorNote)
        .where(CreatorNote.creator_id == creator_id)
        .order_by(desc(CreatorNote.created_at))
    )
    notes = result.scalars().all()
    return [
        {
            "id": str(n.id),
            "content": n.content,
            "note_type": n.note_type,
            "created_at": n.created_at.isoformat(),
            "created_by": n.created_by,
        }
        for n in notes
    ]


@router.post("/creators/{creator_id}/notes")
async def add_creator_note(
    creator_id: UUID,
    content: str,
    db: AsyncSession = Depends(get_db),
):
    """Add a note to a creator."""
    creator = await db.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    note = CreatorNote(
        creator_id=creator_id,
        content=content,
        note_type="manual",
    )
    db.add(note)
    await db.commit()
    return {"added": True}


# ─── TAGS ───

@router.post("/creators/{creator_id}/tags")
async def add_tag(creator_id: UUID, tag: str, db: AsyncSession = Depends(get_db)):
    """Add a tag to a creator."""
    creator_tag = CreatorTag(creator_id=creator_id, tag=tag)
    db.add(creator_tag)
    await db.commit()
    return {"added": True}


@router.delete("/creators/{creator_id}/tags/{tag}")
async def remove_tag(creator_id: UUID, tag: str, db: AsyncSession = Depends(get_db)):
    """Remove a tag from a creator."""
    result = await db.execute(
        select(CreatorTag).where(
            and_(CreatorTag.creator_id == creator_id, CreatorTag.tag == tag)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        await db.delete(existing)
        await db.commit()
    return {"removed": True}


# ─── STATS / DASHBOARD ───

@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    total = (await db.execute(select(func.count(Creator.id)))).scalar() or 0

    # Pipeline breakdown
    pipeline_result = await db.execute(
        select(Creator.pipeline_stage, func.count(Creator.id))
        .group_by(Creator.pipeline_stage)
    )
    pipeline_counts = {row[0]: row[1] for row in pipeline_result}

    # Quality breakdown
    quality_result = await db.execute(
        select(Creator.quality_tier, func.count(Creator.id))
        .group_by(Creator.quality_tier)
    )
    quality_counts = {row[0]: row[1] for row in quality_result}

    # Source breakdown
    source_result = await db.execute(
        select(Creator.source, func.count(Creator.id))
        .group_by(Creator.source)
    )
    source_counts = {row[0]: row[1] for row in source_result}

    # Email coverage
    with_email = (await db.execute(
        select(func.count(Creator.id)).where(Creator.email.isnot(None))
    )).scalar() or 0

    # Discovery searches
    total_searches = (await db.execute(
        select(func.count(DiscoverySearch.id))
    )).scalar() or 0

    return {
        "total_creators": total,
        "with_email": with_email,
        "pipeline": pipeline_counts,
        "quality": quality_counts,
        "sources": source_counts,
        "email_coverage": f"{with_email}/{total}",
        "total_discovery_searches": total_searches,
    }


# ─── ENRICHMENT & OUTREACH STRATEGY ───

@router.get("/apify/status")
async def apify_status():
    """Check Apify integration status."""
    from app.services.apify_service import check_apify_status
    return await check_apify_status()


@router.post("/creators/{creator_id}/enrich")
async def enrich_creator_endpoint(creator_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Start async enrichment on a creator:
    1. Find their email from bio/linktree/web
    2. Analyze their recent content & brand partnerships
    3. Generate personalized outreach strategy with AI

    Returns immediately with status. Poll GET /creators/{id}/enrich/status for progress.
    """
    from app.services.enrichment_service import enrich_creator, get_enrichment_status

    creator = await db.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    # Check if already running
    existing = get_enrichment_status(str(creator_id))
    if existing and existing.get("status") not in ("complete", "failed", None):
        return {
            "creator_id": str(creator_id),
            "status": existing.get("status"),
            "message": "Enrichment already in progress",
        }

    # Fire off enrichment as a background task
    import asyncio
    asyncio.create_task(_background_enrich(creator_id))

    return {
        "creator_id": str(creator_id),
        "status": "started",
        "message": "Enrichment started. Poll /enrich/status for progress.",
    }


@router.get("/creators/{creator_id}/enrich/status")
async def enrich_status(creator_id: UUID):
    """Poll enrichment progress for a creator."""
    from app.services.enrichment_service import get_enrichment_status

    status = get_enrichment_status(str(creator_id))
    if not status:
        return {
            "creator_id": str(creator_id),
            "status": "not_started",
            "step": 0,
            "total_steps": 3,
            "step_label": "Not started",
        }

    return {
        "creator_id": str(creator_id),
        **status,
    }


@router.post("/creators/{creator_id}/find-email")
async def find_email_endpoint(creator_id: UUID, db: AsyncSession = Depends(get_db)):
    """Find a creator's email from their bio, linktree, or web search."""
    from app.services.enrichment_service import find_creator_email

    creator = await db.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    handle = (
        creator.tiktok_handle or creator.instagram_handle or
        creator.youtube_handle or creator.name
    )
    platform = (
        "tiktok" if creator.tiktok_url else
        "instagram" if creator.instagram_url else "unknown"
    )

    result = await find_creator_email(
        handle=handle,
        platform=platform,
        bio=creator.bio or "",
        profile_url=creator.tiktok_url or creator.instagram_url or "",
    )

    # Update creator if email found
    if result.get("primary_email") and not creator.email:
        creator.email = result["primary_email"]
        await db.commit()

    return result


@router.get("/creators/{creator_id}/strategy")
async def get_creator_strategy(creator_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Get the stored outreach strategy for a creator.
    Returns the AI-generated strategy from the most recent enrichment.
    """
    creator = await db.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    ai = creator.ai_analysis if isinstance(creator.ai_analysis, dict) else {}
    strategy = ai.get("outreach_strategy")

    if not strategy:
        return {
            "creator_id": str(creator_id),
            "has_strategy": False,
            "message": "No strategy generated yet. POST /creators/{id}/enrich to generate one.",
        }

    return {
        "creator_id": str(creator_id),
        "creator_name": creator.name,
        "has_strategy": True,
        "last_enriched": ai.get("last_enriched"),
        "strategy": strategy,
    }


@router.post("/creators/{creator_id}/outreach-strategy")
async def generate_strategy_endpoint(creator_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Generate a personalized outreach strategy for a creator.
    Analyzes their content, partnerships, and generates tailored email copy.
    """
    from app.services.enrichment_service import (
        analyze_creator_content, generate_outreach_strategy
    )

    creator = await db.get(Creator, creator_id)
    if not creator:
        raise HTTPException(status_code=404, detail="Creator not found")

    handle = (
        creator.tiktok_handle or creator.instagram_handle or
        creator.youtube_handle or creator.name
    )
    platform = (
        "tiktok" if creator.tiktok_url else
        "instagram" if creator.instagram_url else "unknown"
    )

    # Analyze content
    content_analysis = await analyze_creator_content(
        handle=handle,
        platform=platform,
        profile_url=creator.tiktok_url or creator.instagram_url or "",
    )

    # Generate strategy
    creator_data = {
        "name": creator.name,
        "handle": handle,
        "platform": platform,
        "bio": creator.bio,
        "categories": creator.categories,
        "followers": creator.total_followers,
        "engagement_rate": creator.engagement_rate,
        "email": creator.email,
        "quality_tier": str(creator.quality_tier),
    }

    strategy = await generate_outreach_strategy(creator_data, content_analysis)

    # Store in ai_analysis
    existing = creator.ai_analysis if isinstance(creator.ai_analysis, dict) else {}
    existing["outreach_strategy"] = strategy
    creator.ai_analysis = existing
    await db.commit()

    return {
        "creator_id": str(creator_id),
        "creator_name": creator.name,
        "content_analysis": content_analysis,
        "strategy": strategy,
    }


@router.post("/creators/bulk-enrich")
async def bulk_enrich(
    creator_ids: list[UUID],
    db: AsyncSession = Depends(get_db),
):
    """Enrich multiple creators at once."""
    from app.services.enrichment_service import enrich_creator

    results = {"success": 0, "failed": 0, "details": []}

    for cid in creator_ids:
        creator = await db.get(Creator, cid)
        if not creator:
            results["failed"] += 1
            continue

        try:
            enrichment = await enrich_creator(creator, db)
            results["success"] += 1
            results["details"].append({
                "name": creator.name,
                "email_found": bool(enrichment.get("email_search", {}).get("primary_email")),
                "priority": enrichment.get("outreach_strategy", {}).get("priority_level"),
            })
        except Exception as e:
            results["failed"] += 1
            results["details"].append({"name": creator.name, "error": str(e)})

    return results
