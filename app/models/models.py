"""
Creator Discovery Engine — Database Models

This schema is designed to:
1. Store creators from ANY source (Excel import, scraping, AI discovery)
2. Map cleanly to existing ClickUp custom fields in Creator Pipeline/Pool
3. Track outreach conversations (Gmail integration)
4. Support intelligent search and filtering
5. Log discovery searches for learning and optimization
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String, Text, Integer, Float, Boolean, DateTime, JSON,
    ForeignKey, Index, UniqueConstraint, Enum as SAEnum,
    TypeDecorator,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

import json as _json


# ─── CROSS-DB COMPATIBLE TYPES ───
# These work on both SQLite (local dev) and PostgreSQL (production)

class JSONB(TypeDecorator):
    """JSONB-compatible type that works on SQLite and PostgreSQL."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return _json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return _json.loads(value)
        return None


class UUIDType(TypeDecorator):
    """UUID type that stores as string on SQLite, native UUID on PostgreSQL."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value) if not isinstance(value, uuid.UUID) else value
        return None


# ─── ENUMS ───

import enum

class CreatorSource(str, enum.Enum):
    EXCEL_IMPORT = "excel_import"
    AI_DISCOVERY = "ai_discovery"
    WEB_SCRAPE = "web_scrape"
    REDDIT_SCRAPE = "reddit_scrape"
    UGC_MARKETPLACE = "ugc_marketplace"
    MANUAL_ENTRY = "manual_entry"
    CLICKUP_SYNC = "clickup_sync"

class PipelineStage(str, enum.Enum):
    DISCOVERED = "discovered"         # Just found, not yet reviewed
    PROSPECT = "prospect"             # Reviewed, looks promising
    CONTACTED = "contacted"           # First outreach sent
    REPLIED = "replied"               # They responded
    NEGOTIATING = "negotiating"       # Discussing terms
    AGREED = "agreed"                 # Deal confirmed
    PRODUCING = "producing"           # Creating content
    COMPLETED = "completed"           # Deliverables received
    INACTIVE = "inactive"             # Paused or ended
    DECLINED = "declined"             # They said no

class QualityTier(str, enum.Enum):
    ELITE = "Elite"
    HIGH = "High"
    GOOD = "Good"
    OK = "Ok"
    POOR = "Poor"
    UNRATED = "Unrated"

class OutreachStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    REPLIED = "replied"
    BOUNCED = "bounced"


# ─── CORE MODELS ───

class Creator(Base):
    """
    Central creator profile. One record per unique creator.
    Maps to ClickUp Creator Pipeline custom fields.
    """
    __tablename__ = "creators"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ─── Identity ───
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    age: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # ─── Location ───
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), default="US")

    # ─── Social Profiles ───
    tiktok_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tiktok_handle: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tiktok_followers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    instagram_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    instagram_handle: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    instagram_followers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    youtube_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    youtube_handle: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    youtube_subscribers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    twitter_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    twitter_handle: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    twitter_followers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    facebook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ─── Content & Niche ───
    categories: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    # e.g. ["Doctor", "Health", "Wellness", "Mom", "Gen Z"]

    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    work_examples_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ─── Demographics & Lifestyle Tags (from your Excel) ───
    has_kids: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    has_pets: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    has_lawn: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    has_modern_home: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # ─── Business / Rates ───
    hero_video_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    whitelisting_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    whitelisting_rate_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    whitelisting_handle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    whitelisting_access: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agreed_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    agreed_deliverable: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ─── Pipeline & Status ───
    pipeline_stage: Mapped[str] = mapped_column(
        SAEnum(PipelineStage), default=PipelineStage.DISCOVERED
    )
    quality_tier: Mapped[str] = mapped_column(
        SAEnum(QualityTier), default=QualityTier.UNRATED
    )
    is_core_team: Mapped[bool] = mapped_column(Boolean, default=False)
    msa_signed: Mapped[bool] = mapped_column(Boolean, default=False)
    msa_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ─── Discovery Metadata ───
    source: Mapped[str] = mapped_column(SAEnum(CreatorSource), default=CreatorSource.MANUAL_ENTRY)
    source_details: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # e.g. {"search_query": "doctors heart health", "platform": "tiktok", "subreddit": "r/UGCcreators"}

    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # AI-computed 0-100 score for fit with Luma products

    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Structured AI analysis: {"credentials_verified": true, "content_quality": "high", ...}

    engagement_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_followers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ─── ClickUp Sync ───
    clickup_task_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    clickup_list: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    clickup_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ─── Drive / Assets ───
    drive_folder_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ─── Raw Import Data (preserve original spreadsheet data) ───
    raw_import_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ─── Relationships ───
    outreach_emails: Mapped[list["OutreachEmail"]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    notes: Mapped[list["CreatorNote"]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    tags: Mapped[list["CreatorTag"]] = relationship(back_populates="creator", cascade="all, delete-orphan")
    discovery_results: Mapped[list["DiscoveryResult"]] = relationship(back_populates="creator")

    __table_args__ = (
        Index("ix_creators_email", "email"),
        Index("ix_creators_pipeline", "pipeline_stage"),
        Index("ix_creators_quality", "quality_tier"),
        Index("ix_creators_source", "source"),
        Index("ix_creators_categories", "categories"),
        Index("ix_creators_relevance", "relevance_score"),
        Index("ix_creators_name", "name"),
    )


class CreatorTag(Base):
    """Flexible tagging system for creators."""
    __tablename__ = "creator_tags"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"))
    tag: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    creator: Mapped["Creator"] = relationship(back_populates="tags")

    __table_args__ = (
        UniqueConstraint("creator_id", "tag", name="uq_creator_tag"),
        Index("ix_tags_tag", "tag"),
    )


class CreatorNote(Base):
    """Activity log and notes for each creator."""
    __tablename__ = "creator_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    note_type: Mapped[str] = mapped_column(String(50), default="manual")
    # Types: manual, status_change, email_sent, email_received, import, ai_analysis
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    creator: Mapped["Creator"] = relationship(back_populates="notes")


class OutreachEmail(Base):
    """Email outreach tracking — syncs with Gmail."""
    __tablename__ = "outreach_emails"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("creators.id", ondelete="CASCADE"))

    # Email content
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    from_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(SAEnum(OutreachStatus), default=OutreachStatus.DRAFT)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    replied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Gmail integration
    gmail_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gmail_thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Template reference
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("email_templates.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    creator: Mapped["Creator"] = relationship(back_populates="outreach_emails")
    template: Mapped[Optional["EmailTemplate"]] = relationship()


class EmailTemplate(Base):
    """Reusable email templates for outreach."""
    __tablename__ = "email_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_template: Mapped[str] = mapped_column(String(500), nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    # Templates use {{creator_name}}, {{category}}, {{platform}}, etc.
    template_type: Mapped[str] = mapped_column(String(50), default="first_touch")
    # Types: first_touch, follow_up_1, follow_up_2, negotiation, confirmation
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ─── DISCOVERY ENGINE MODELS ───

class DiscoverySearch(Base):
    """Log of every discovery search run — for learning and optimization."""
    __tablename__ = "discovery_searches"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    # Natural language query: "doctors who talk about heart health on TikTok"

    parsed_intent: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # AI-parsed: {"niche": "doctor", "topic": "heart health", "platform": "tiktok", ...}

    platforms_searched: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    filters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # {"follower_min": 10000, "follower_max": 500000, "engagement_min": 2.0}

    results_count: Mapped[int] = mapped_column(Integer, default=0)
    results_saved: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(50), default="pending")
    # pending, searching, analyzing, complete, failed

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    results: Mapped[list["DiscoveryResult"]] = relationship(back_populates="search", cascade="all, delete-orphan")


class DiscoveryResult(Base):
    """Individual result from a discovery search, before being saved as a creator."""
    __tablename__ = "discovery_results"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    search_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("discovery_searches.id", ondelete="CASCADE"))

    # Raw discovered data
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    handle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    profile_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    followers: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # AI analysis
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ai_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    categories: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # Source tracking
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # web_search, reddit_scrape, ugc_marketplace, hashtag_search, etc.
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Link to saved creator (if user saves this result)
    creator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("creators.id"), nullable=True
    )
    saved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    search: Mapped["DiscoverySearch"] = relationship(back_populates="results")
    creator: Mapped[Optional["Creator"]] = relationship(back_populates="discovery_results")

    __table_args__ = (
        Index("ix_discovery_platform", "platform"),
        Index("ix_discovery_relevance", "relevance_score"),
    )


# ─── SCRAPER STATE MODELS ───

class ScraperJob(Base):
    """Track background scraping jobs."""
    __tablename__ = "scraper_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Types: reddit_scan, ugc_marketplace_scan, hashtag_research, profile_enrich
    target: Mapped[str] = mapped_column(Text, nullable=False)
    # e.g. "r/UGCcreators" or "tiktok:#guthealth"
    status: Mapped[str] = mapped_column(String(50), default="pending")
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ─── BLACKLIST ───

class BlacklistedCreator(Base):
    """Creators the coordinator has permanently rejected. Never show in discovery results."""
    __tablename__ = "blacklisted_creators"

    id: Mapped[uuid.UUID] = mapped_column(UUIDType(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    handle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blacklisted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_blacklist_name", "name"),
        Index("ix_blacklist_handle", "handle"),
    )
