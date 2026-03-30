"""
Excel/CSV Import Service

Handles importing creator data from spreadsheets into the database.
Smart column mapping handles your existing format plus variations.
"""

import io
import re
import logging
from typing import Optional
from datetime import datetime

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import Creator, CreatorSource, CreatorNote
from app.models.schemas import ImportResult

logger = logging.getLogger(__name__)


# ─── COLUMN MAPPING ───
# Maps various column name patterns to our database fields.
# Handles your existing "CREATORSSSSSS" format plus common variations.

COLUMN_MAP = {
    # Name
    r"influencer\s*name|creator\s*name|^name$|full\s*name": "name",

    # Contact
    r"^email|e-?mail\s*address": "email",
    r"phone|phone\s*number|mobile": "phone",

    # Demographics
    r"^age$": "age",
    r"^gender$": "gender",
    r"^address$|mailing\s*address": "address",
    r"^city$": "city",
    r"^state$": "state",
    r"^location$": "location",

    # Social URLs
    r"tiktok|tik\s*tok\s*page": "tiktok_url",
    r"ig\s*page|instagram|insta\s*page": "instagram_url",
    r"yt\s*page|youtube|you\s*tube\s*page": "youtube_url",
    r"fb\s*page|facebook": "facebook_url",
    r"twitter|x\.com": "twitter_url",
    r"linkedin": "linkedin_url",

    # Handle
    r"influencer\s*handle|^handle$|creator\s*handle": "handle",

    # Content
    r"content\s*categor|categor|niche": "categories_raw",
    r"other\s*content\s*notes|content\s*notes|notes": "content_notes",
    r"portfolio|portfolio\s*link": "portfolio_url",
    r"work\s*examples|work\s*example": "work_examples_url",

    # Demographics / Lifestyle
    r"kids|has\s*kids": "has_kids",
    r"pets|has\s*pets": "has_pets",
    r"lawn|has\s*lawn": "has_lawn",
    r"modern\s*home": "has_modern_home",

    # Business
    r"per\s*hero|hero\s*video|hero\s*rate": "hero_video_rate",
    r"wl\s*rate|whitelisting\s*rate": "whitelisting_rate",
    r"wl\s*rate\s*type|whitelisting\s*rate\s*type": "whitelisting_rate_type",
    r"wl\s*access|whitelisting\s*access": "whitelisting_access",
    r"whitelisting\s*handle|wl\s*handle": "whitelisting_handle",
    r"payment\s*method": "payment_method",
    r"payment\s*notes": "payment_notes",
    r"agreed\s*rate": "agreed_rate",
    r"agreed\s*deliverable": "agreed_deliverable",

    # Status
    r"^status$": "status_raw",
    r"quality|quality\s*ranking": "quality_raw",
    r"core\s*creator|core\s*team": "core_team_raw",
    r"msa\s*signed": "msa_signed_raw",
    r"msa\s*date": "msa_date_raw",
    r"date\s*sourced": "date_sourced",

    # New Creator Selects
    r"new\s*creator\s*selects": "new_selects_raw",
    r"drop\s*date": "drop_date",
    r"^drop\?$|^drop$": "drop_raw",

    # Drive
    r"drive\s*folder": "drive_folder_url",
}


def map_columns(df: pd.DataFrame) -> dict:
    """Map DataFrame columns to our field names using fuzzy matching."""
    mapping = {}

    for col in df.columns:
        col_lower = col.strip().lower()
        for pattern, field_name in COLUMN_MAP.items():
            if re.search(pattern, col_lower, re.IGNORECASE):
                mapping[col] = field_name
                break

    return mapping


def parse_bool(val) -> Optional[bool]:
    """Parse various boolean representations."""
    if pd.isna(val):
        return None
    s = str(val).strip().lower()
    if s in ("yes", "true", "1", "y"):
        return True
    if s in ("no", "false", "0", "n"):
        return False
    return None


def parse_currency(val) -> Optional[float]:
    """Parse currency strings like '$300.00' to float."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    s = re.sub(r"[^0-9.]", "", s)
    try:
        return float(s) if s else None
    except ValueError:
        return None


def parse_categories(val) -> list[str]:
    """Parse comma-separated category strings into a clean list."""
    if pd.isna(val):
        return []
    s = str(val).strip()
    cats = [c.strip() for c in s.split(",") if c.strip()]
    # Clean up common variations
    clean = []
    for cat in cats:
        cat = cat.strip()
        if cat.lower() == "all":
            continue  # Skip generic "All" category
        clean.append(cat)
    return clean


def map_quality(val) -> str:
    """Map quality ranking to our enum."""
    if pd.isna(val):
        return "Unrated"
    s = str(val).strip().lower()
    quality_map = {
        "elite": "Elite",
        "high": "High",
        "good": "Good",
        "ok": "Ok",
        "okay": "Ok",
        "poor": "Poor",
        "low": "Poor",
    }
    return quality_map.get(s, "Unrated")


def map_pipeline_stage(val) -> str:
    """Map status strings to pipeline stages."""
    if pd.isna(val):
        return "discovered"
    s = str(val).strip().lower()
    if "active" in s:
        return "producing"
    if "inactive" in s:
        return "inactive"
    if "prospect" in s:
        return "prospect"
    if "contact" in s:
        return "contacted"
    return "discovered"


def extract_handle_from_url(url: str) -> Optional[str]:
    """Extract handle from a social media URL."""
    if not url:
        return None
    patterns = [
        r"(?:tiktok\.com|instagram\.com|twitter\.com|x\.com)/@?([^/?\s]+)",
        r"youtube\.com/(?:@|channel/|c/)([^/?\s]+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, url, re.IGNORECASE)
        if m:
            return f"@{m.group(1)}"
    return None


# ─── MAIN IMPORT FUNCTION ───

async def import_spreadsheet(
    file_content: bytes,
    filename: str,
    db: AsyncSession,
) -> ImportResult:
    """
    Import creators from an Excel/CSV file.

    1. Read file (CSV or Excel)
    2. Map columns to our schema
    3. Parse and clean each row
    4. Deduplicate against existing database
    5. Create creator records
    """

    # Step 1: Read file
    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_content))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_content))
        else:
            raise ValueError(f"Unsupported file format: {filename}")
    except Exception as e:
        return ImportResult(
            total_rows=0, imported=0, duplicates_skipped=0,
            errors=[{"row": 0, "error": f"Failed to read file: {str(e)}"}]
        )

    # Drop completely empty rows
    df = df.dropna(how="all")
    total_rows = len(df)

    # Step 2: Map columns
    col_mapping = map_columns(df)
    logger.info(f"Column mapping: {col_mapping}")

    # Step 3: Get existing emails for dedup
    existing_emails = set()
    result = await db.execute(select(Creator.email).where(Creator.email.isnot(None)))
    for row in result.scalars():
        if row:
            existing_emails.add(row.lower())

    # Step 4: Process rows
    imported_count = 0
    duplicates = 0
    errors = []
    created_creators = []

    for idx, row in df.iterrows():
        try:
            # Build mapped data dict
            data = {}
            for original_col, mapped_field in col_mapping.items():
                val = row.get(original_col)
                if not pd.isna(val):
                    data[mapped_field] = val

            # Skip rows without a name
            name = data.get("name", "")
            if not name or pd.isna(name):
                continue

            name = str(name).strip()
            email = str(data.get("email", "")).strip() if data.get("email") else None

            # Dedup check
            if email and email.lower() in existing_emails:
                duplicates += 1
                continue

            # Parse location from combined field
            location = data.get("location", "")
            address = data.get("address", "")
            if location and not address:
                address = str(location)

            # Build creator
            creator = Creator(
                name=name,
                email=email,
                phone=str(data.get("phone", "")).strip() or None,
                age=str(data.get("age", "")).strip() or None,
                gender=str(data.get("gender", "")).strip() or None,
                address=str(address).strip() or None,
                city=str(data.get("city", "")).strip() or None,
                state=str(data.get("state", "")).strip() or None,

                # Social URLs
                tiktok_url=str(data.get("tiktok_url", "")).strip() or None,
                tiktok_handle=extract_handle_from_url(str(data.get("tiktok_url", ""))),
                instagram_url=str(data.get("instagram_url", "")).strip() or None,
                instagram_handle=extract_handle_from_url(str(data.get("instagram_url", ""))),
                youtube_url=str(data.get("youtube_url", "")).strip() or None,
                youtube_handle=extract_handle_from_url(str(data.get("youtube_url", ""))),
                facebook_url=str(data.get("facebook_url", "")).strip() or None,
                twitter_url=str(data.get("twitter_url", "")).strip() or None,
                linkedin_url=str(data.get("linkedin_url", "")).strip() or None,

                # Content
                categories=parse_categories(data.get("categories_raw")),
                content_notes=str(data.get("content_notes", "")).strip() or None,
                portfolio_url=str(data.get("portfolio_url", "")).strip() or None,
                work_examples_url=str(data.get("work_examples_url", "")).strip() or None,

                # Demographics
                has_kids=parse_bool(data.get("has_kids")),
                has_pets=parse_bool(data.get("has_pets")),
                has_lawn=parse_bool(data.get("has_lawn")),
                has_modern_home=parse_bool(data.get("has_modern_home")),

                # Business
                hero_video_rate=parse_currency(data.get("hero_video_rate")),
                whitelisting_rate=parse_currency(data.get("whitelisting_rate")),
                whitelisting_rate_type=str(data.get("whitelisting_rate_type", "")).strip() or None,
                whitelisting_access=parse_bool(data.get("whitelisting_access")),
                whitelisting_handle=str(data.get("whitelisting_handle", "")).strip() or None,
                payment_method=str(data.get("payment_method", "")).strip() or None,
                payment_notes=str(data.get("payment_notes", "")).strip() or None,
                agreed_rate=parse_currency(data.get("agreed_rate")),
                agreed_deliverable=str(data.get("agreed_deliverable", "")).strip() or None,

                # Status
                pipeline_stage=map_pipeline_stage(data.get("status_raw")),
                quality_tier=map_quality(data.get("quality_raw")),
                is_core_team=parse_bool(data.get("core_team_raw")) or False,
                msa_signed=parse_bool(data.get("msa_signed_raw")) or False,

                # Source
                source=CreatorSource.EXCEL_IMPORT,
                source_details={"filename": filename, "row": idx + 2},

                # Preserve raw data
                raw_import_data={k: str(v) for k, v in row.to_dict().items() if not pd.isna(v)},
            )

            db.add(creator)

            # Add import note via relationship so FK is resolved on flush
            note = CreatorNote(
                content=f"Imported from {filename} (row {idx + 2})",
                note_type="import",
            )
            creator.notes.append(note)

            if email:
                existing_emails.add(email.lower())

            imported_count += 1

        except Exception as e:
            errors.append({"row": idx + 2, "error": str(e)})
            logger.error(f"Row {idx + 2} import error: {e}")

    # Commit all
    await db.commit()

    logger.info(
        f"Import complete: {imported_count}/{total_rows} imported, "
        f"{duplicates} duplicates, {len(errors)} errors"
    )

    return ImportResult(
        total_rows=total_rows,
        imported=imported_count,
        duplicates_skipped=duplicates,
        errors=errors,
    )
