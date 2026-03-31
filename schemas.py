"""
Pydantic schemas for API request/response validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# ─── CREATOR SCHEMAS ───

class CreatorBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    age: Optional[str] = None
    gender: Optional[str] = None

    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "US"

    tiktok_url: Optional[str] = None
    tiktok_handle: Optional[str] = None
    tiktok_followers: Optional[int] = None
    instagram_url: Optional[str] = None
    instagram_handle: Optional[str] = None
    instagram_followers: Optional[int] = None
    youtube_url: Optional[str] = None
    youtube_handle: Optional[str] = None
    youtube_subscribers: Optional[int] = None
    twitter_url: Optional[str] = None
    twitter_handle: Optional[str] = None
    twitter_followers: Optional[int] = None
    facebook_url: Optional[str] = None
    linkedin_url: Optional[str] = None

    categories: list[str] = []
    bio: Optional[str] = None
    content_notes: Optional[str] = None
    portfolio_url: Optional[str] = None
    work_examples_url: Optional[str] = None

    has_kids: Optional[bool] = None
    has_pets: Optional[bool] = None
    has_lawn: Optional[bool] = None
    has_modern_home: Optional[bool] = None

    hero_video_rate: Optional[float] = None
    whitelisting_rate: Optional[float] = None
    whitelisting_rate_type: Optional[str] = None
    payment_method: Optional[str] = None

    pipeline_stage: str = "discovered"
    quality_tier: str = "Unrated"
    is_core_team: bool = False


class CreatorCreate(CreatorBase):
    source: str = "manual_entry"
    source_details: Optional[dict] = None


class CreatorUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    pipeline_stage: Optional[str] = None
    quality_tier: Optional[str] = None
    categories: Optional[list[str]] = None
    hero_video_rate: Optional[float] = None
    whitelisting_rate: Optional[float] = None
    content_notes: Optional[str] = None
    is_core_team: Optional[bool] = None


class CreatorResponse(CreatorBase):
    id: UUID
    source: str
    source_details: Optional[dict] = None
    relevance_score: Optional[float] = None
    engagement_rate: Optional[float] = None
    total_followers: Optional[int] = None
    ai_analysis: Optional[dict] = None
    clickup_task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CreatorListResponse(BaseModel):
    creators: list[CreatorResponse]
    total: int
    page: int
    per_page: int


# ─── DISCOVERY SCHEMAS ───

class DiscoverySearchRequest(BaseModel):
    """What the influencer coordinator submits."""
    query: str = Field(..., description="Natural language search query", min_length=3)
    platforms: list[str] = Field(
        default=["tiktok", "instagram", "youtube"],
        description="Platforms to search"
    )
    search_mode: str = Field(
        default="general",
        description="Search mode: 'general' or 'doctor' for specialized medical professional discovery"
    )
    follower_min: Optional[int] = None
    follower_max: Optional[int] = None
    engagement_min: Optional[float] = None
    categories: list[str] = []
    max_results: int = Field(default=20, ge=1, le=100)


class DiscoveryResultResponse(BaseModel):
    id: UUID
    name: str
    handle: Optional[str] = None
    platform: str
    profile_url: Optional[str] = None
    bio: Optional[str] = None
    email: Optional[str] = None
    followers: Optional[int] = None
    engagement_rate: Optional[float] = None
    relevance_score: Optional[float] = None
    categories: list[str] = []
    ai_analysis: Optional[dict] = None
    source_type: str
    source_url: Optional[str] = None
    creator_id: Optional[UUID] = None
    saved_at: Optional[datetime] = None
    discovered_at: datetime

    class Config:
        from_attributes = True


class DiscoverySearchResponse(BaseModel):
    search_id: UUID
    query: str
    status: str
    parsed_intent: Optional[dict] = None
    platforms_searched: list[str] = []
    results: list[DiscoveryResultResponse] = []
    results_count: int = 0
    started_at: datetime
    completed_at: Optional[datetime] = None


# ─── OUTREACH SCHEMAS ───

class OutreachEmailCreate(BaseModel):
    creator_id: UUID
    subject: str
    body: str
    template_id: Optional[UUID] = None


class OutreachEmailResponse(BaseModel):
    id: UUID
    creator_id: UUID
    subject: str
    body: str
    to_email: str
    status: str
    sent_at: Optional[datetime] = None
    gmail_message_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class EmailTemplateCreate(BaseModel):
    name: str
    subject_template: str
    body_template: str
    template_type: str = "first_touch"


class EmailTemplateResponse(BaseModel):
    id: UUID
    name: str
    subject_template: str
    body_template: str
    template_type: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── IMPORT SCHEMAS ───

class ImportResult(BaseModel):
    total_rows: int
    imported: int
    duplicates_skipped: int
    errors: list[dict] = []
    creators: list[CreatorResponse] = []


# ─── FILTER / SEARCH SCHEMAS ───

class CreatorFilter(BaseModel):
    search: Optional[str] = None
    pipeline_stage: Optional[str] = None
    quality_tier: Optional[str] = None
    source: Optional[str] = None
    categories: list[str] = []
    platform: Optional[str] = None  # has presence on this platform
    follower_min: Optional[int] = None
    follower_max: Optional[int] = None
    is_core_team: Optional[bool] = None
    has_email: Optional[bool] = None
    page: int = 1
    per_page: int = 50
    sort_by: str = "created_at"
    sort_dir: str = "desc"


# ─── ENRICHMENT SCHEMAS ───

class EnrichmentStatus(BaseModel):
    """Tracks progress of async enrichment pipeline."""
    creator_id: UUID
    status: str  # pending, finding_email, analyzing_content, generating_strategy, complete, failed
    step: int  # 1-3
    total_steps: int = 3
    step_label: str = ""
    result: Optional[dict] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
