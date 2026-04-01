"""
ClickUp Integration Service

Syncs creators between our database and ClickUp's Creator Pipeline.

ClickUp structure (Marketing 2.0 → Influencer Partnerships):
  - Creator Pool (901815616527) — prospects/discovered
  - Creator Pipeline (901815310001) — active relationships
  - Creator Content (901815310246) — producing content

Custom field IDs from Creator Pipeline:
  - Category: 04fc1e49-f53f-4a48-b959-50dd7f92fd2a (labels)
  - Email: e2b74079-1904-4eb7-bb37-4b1655484618
  - Phone: ee94540e-1f5f-49eb-a4c6-c3ba88adfb6e
  - Age: c00891cc-bc43-4aef-90a5-27211d0c80a4
  - Gender: f06c99fa-864d-4040-9f6a-f548579fc7fc
  - City: 523b20e0-9068-4325-a72a-eaf5accb276f
  - State: 68cc70c5-91e0-4596-aa86-87e26755e7e0
  - Quality: 7c527142-5eb0-4afb-8e08-c4cdfdd293b1 (dropdown)
  - Agreed Rate: 7fb67b3d-a32c-491d-bf70-36a653632c47 (currency)
  - Agreed Deliverable: 5d4b3cb8-be14-450f-92b6-e2269efc6774
  - Hero Rate: (mapped from Per Hero Video field)
  - WL Rate: 67f092e5-d34b-4e68-bbe7-85921693b15e (currency)
  - WL Access: 0c273930-346b-4667-bab6-5e8c3ffb0cf9 (checkbox)
  - WL Handle: 00b6c6ae-cbcf-4da0-b9aa-e3b0125234e3
  - Portfolio: 8f283c6e-5bee-4740-94ab-044c9495ef83 (URL)
  - Drive Folder: 8784aecc-b5b6-4974-a3a2-080ebe3c4bb3 (URL)
  - Product Status: f9506f8c-d116-4be9-afd5-59ba93bf0d9a (dropdown)
  - Delivery Time: 5007ce04-f0c3-46d4-87a9-c2d7298444ce (dropdown)
  - Address: 38bcaae7-92cf-4edc-9816-994d8fcb3d9b (location)
  - Production Months: be844b3a-e37c-4bca-a123-12a1345ac6ed (labels)
  - Production Output: daedc825-9a8c-4b36-bc9c-38db2982abd6 (number)
  - Payment Info: 7247842a-5cd8-4c34-b6c8-a19efb393a98
"""

import logging
from typing import Optional
from datetime import datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models.models import Creator, CreatorNote

logger = logging.getLogger(__name__)
settings = get_settings()

# ClickUp List IDs
CREATOR_POOL_LIST_ID = "901815616527"
CREATOR_PIPELINE_LIST_ID = "901815310001"
CREATOR_CONTENT_LIST_ID = "901815310246"

# Category label IDs for mapping
CATEGORY_LABEL_IDS = {
    "Doctor": "03984ab4-7d81-4220-99f1-5ecb00a4c4ec",
    "Lifestyle": "f6912e5f-5e6a-401d-8a20-b8d3127dd734",
    "Gen X": "d4457bfa-15d8-4c72-8d88-08046bfaeb97",
    "Millennial": "b43ed9d6-2d55-422d-bb2e-cd05dd1f5e21",
    "Fitness": "d0d026a2-1b83-4bf0-97d1-cef942e505bf",
    "Healthy Living": "fdeade39-c921-4cea-ad9c-822a3bb48c65",
    "Podcaster": "5a226beb-48ab-4cd2-bb3d-809e8aacad83",
    "Mom": "8f0e8dd1-2ea2-47a0-8af2-871dba7b03c7",
    "Dad": "1511c821-40a9-4b30-8021-d635081701c6",
    "Pets": "3a8fe00a-9abe-4ae6-92e2-bde3826b0b50",
    "Couple Content": "0d63cde7-68f4-485e-8d90-a1058d10efd9",
    "Comedy": "9646ee5d-1e10-4aa1-8ced-7bd67a01326e",
    "Beauty": "d2ed2ac6-6ba3-4450-8d9d-f2e106116d1f",
    "Wellness": "596932c1-8868-45e4-8129-db57f9c1b8f0",
    "Actor/Actress": "dbf379d4-3a5c-4628-a7ff-0c3ce6ac9992",
    "Nurse": "6c4af766-18b5-4cc4-ac30-3ef523edf6ea",
}

# Quality dropdown option IDs
QUALITY_OPTION_IDS = {
    "High": "7dad034a-318d-4420-a29c-1332a22ec26d",
    "Medium": "f1de16a9-634c-4142-8ae7-c7a8e54e033d",
    "Low": "8a57b3c7-95b0-4db8-bc0e-54f9f7cdfbcf",
    "Do not use": "bc3cf429-4d23-4d13-acd1-8f5f4d03d03b",
}


class ClickUpService:
    """Manages bidirectional sync between our DB and ClickUp."""

    def __init__(self):
        self.base_url = "https://api.clickup.com/api/v2"
        self.client = httpx.AsyncClient(
            timeout=30,
            headers={
                "Authorization": settings.clickup_api_token,
                "Content-Type": "application/json",
            }
        )

    def _determine_target_list(self, creator: Creator) -> str:
        """Determine which ClickUp list a creator should go to."""
        stage = creator.pipeline_stage
        if stage in ("discovered", "prospect"):
            return CREATOR_POOL_LIST_ID
        elif stage in ("producing", "completed"):
            return CREATOR_CONTENT_LIST_ID
        else:
            return CREATOR_PIPELINE_LIST_ID

    def _map_categories_to_labels(self, categories: list[str]) -> list[str]:
        """Map our category strings to ClickUp label IDs."""
        label_ids = []
        for cat in categories:
            # Try exact match first
            if cat in CATEGORY_LABEL_IDS:
                label_ids.append(CATEGORY_LABEL_IDS[cat])
            else:
                # Try fuzzy match
                cat_lower = cat.lower()
                for label_name, label_id in CATEGORY_LABEL_IDS.items():
                    if label_name.lower() in cat_lower or cat_lower in label_name.lower():
                        label_ids.append(label_id)
                        break
        return label_ids

    def _build_custom_fields(self, creator: Creator) -> list[dict]:
        """Build ClickUp custom field values from a creator record."""
        fields = []

        if creator.email:
            fields.append({
                "id": "e2b74079-1904-4eb7-bb37-4b1655484618",
                "value": creator.email,
            })

        if creator.phone:
            fields.append({
                "id": "ee94540e-1f5f-49eb-a4c6-c3ba88adfb6e",
                "value": creator.phone,
            })

        if creator.gender:
            fields.append({
                "id": "f06c99fa-864d-4040-9f6a-f548579fc7fc",
                "value": creator.gender,
            })

        if creator.city:
            fields.append({
                "id": "523b20e0-9068-4325-a72a-eaf5accb276f",
                "value": creator.city,
            })

        if creator.state:
            fields.append({
                "id": "68cc70c5-91e0-4596-aa86-87e26755e7e0",
                "value": creator.state,
            })

        if creator.agreed_rate:
            fields.append({
                "id": "7fb67b3d-a32c-491d-bf70-36a653632c47",
                "value": creator.agreed_rate,
            })

        if creator.whitelisting_rate:
            fields.append({
                "id": "67f092e5-d34b-4e68-bbe7-85921693b15e",
                "value": creator.whitelisting_rate,
            })

        if creator.whitelisting_access is not None:
            fields.append({
                "id": "0c273930-346b-4667-bab6-5e8c3ffb0cf9",
                "value": creator.whitelisting_access,
            })

        if creator.whitelisting_handle:
            fields.append({
                "id": "00b6c6ae-cbcf-4da0-b9aa-e3b0125234e3",
                "value": creator.whitelisting_handle,
            })

        if creator.portfolio_url:
            fields.append({
                "id": "8f283c6e-5bee-4740-94ab-044c9495ef83",
                "value": creator.portfolio_url,
            })

        if creator.drive_folder_url:
            fields.append({
                "id": "8784aecc-b5b6-4974-a3a2-080ebe3c4bb3",
                "value": creator.drive_folder_url,
            })

        # Category labels
        if creator.categories:
            label_ids = self._map_categories_to_labels(creator.categories)
            if label_ids:
                fields.append({
                    "id": "04fc1e49-f53f-4a48-b959-50dd7f92fd2a",
                    "value": label_ids,
                })

        # Quality dropdown
        quality_map = {
            "Elite": "7dad034a-318d-4420-a29c-1332a22ec26d",
            "High": "7dad034a-318d-4420-a29c-1332a22ec26d",
            "Good": "f1de16a9-634c-4142-8ae7-c7a8e54e033d",
            "Ok": "8a57b3c7-95b0-4db8-bc0e-54f9f7cdfbcf",
            "Poor": "bc3cf429-4d23-4d13-acd1-8f5f4d03d03b",
        }
        if creator.quality_tier in quality_map:
            fields.append({
                "id": "7c527142-5eb0-4afb-8e08-c4cdfdd293b1",
                "value": quality_map[creator.quality_tier],
            })

        return fields

    async def push_creator(self, creator: Creator, db: AsyncSession) -> Optional[str]:
        """Push a creator to ClickUp as a task."""
        target_list = self._determine_target_list(creator)
        custom_fields = self._build_custom_fields(creator)

        # Build task description
        description_parts = []
        if creator.bio:
            description_parts.append(f"**Bio:** {creator.bio}")
        if creator.content_notes:
            description_parts.append(f"**Notes:** {creator.content_notes}")
        if creator.tiktok_url:
            description_parts.append(f"**TikTok:** {creator.tiktok_url}")
        if creator.instagram_url:
            description_parts.append(f"**Instagram:** {creator.instagram_url}")
        if creator.youtube_url:
            description_parts.append(f"**YouTube:** {creator.youtube_url}")
        if creator.relevance_score:
            description_parts.append(f"**AI Relevance Score:** {creator.relevance_score}/100")
        if creator.ai_analysis:
            fit = creator.ai_analysis.get("content_fit")
            if fit:
                description_parts.append(f"**Content Fit:** {fit}")

        payload = {
            "name": creator.name,
            "description": "\n".join(description_parts),
            "custom_fields": custom_fields,
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/list/{target_list}/task",
                json=payload,
            )

            if response.status_code in (200, 201):
                task_data = response.json()
                task_id = task_data.get("id")

                # Update creator with ClickUp reference
                creator.clickup_task_id = task_id
                creator.clickup_list = target_list
                creator.clickup_synced_at = datetime.utcnow()

                # Add note
                note = CreatorNote(
                    creator_id=creator.id,
                    content=f"Pushed to ClickUp (Task: {task_id}, List: {target_list})",
                    note_type="status_change",
                )
                db.add(note)
                await db.commit()

                logger.info(f"Pushed creator {creator.name} to ClickUp: {task_id}")
                return task_id
            else:
                logger.error(f"ClickUp push failed: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"ClickUp push error: {e}")
            return None

    async def sync_status_from_clickup(self, creator: Creator, db: AsyncSession) -> bool:
        """Pull latest status from ClickUp for a creator."""
        if not creator.clickup_task_id:
            return False

        try:
            response = await self.client.get(
                f"{self.base_url}/task/{creator.clickup_task_id}"
            )

            if response.status_code == 200:
                task_data = response.json()
                status = task_data.get("status", {}).get("status", "")

                # Map ClickUp status back to our pipeline stages
                status_map = {
                    "open": "prospect",
                    "in progress": "contacted",
                    "review": "negotiating",
                    "complete": "completed",
                    "closed": "inactive",
                }
                if status.lower() in status_map:
                    creator.pipeline_stage = status_map[status.lower()]

                creator.clickup_synced_at = datetime.utcnow()
                await db.commit()
                return True

            return False

        except Exception as e:
            logger.error(f"ClickUp sync error: {e}")
            return False

    async def bulk_push(self, creators: list[Creator], db: AsyncSession) -> dict:
        """Push multiple creators to ClickUp."""
        results = {"success": 0, "failed": 0, "errors": []}

        for creator in creators:
            if creator.clickup_task_id:
                continue  # Already synced

            task_id = await self.push_creator(creator, db)
            if task_id:
                results["success"] += 1
            else:
                results["failed"] += 1
                results["errors"].append(creator.name)

        return results

    async def push_discovery_result(self, result_data: dict) -> Optional[dict]:
        """
        Push a discovery result directly to ClickUp Creator Pool.
        Does NOT require a saved Creator record — works with raw discovery data.
        Returns {"task_id": ..., "task_url": ...} or None on failure.
        """
        ai = result_data.get("ai_analysis") or {}
        name = result_data.get("name", "Unknown")
        handle = result_data.get("handle", "")
        platform = result_data.get("platform", "unknown")
        profile_url = result_data.get("profile_url", "")
        followers = result_data.get("followers")
        score = result_data.get("relevance_score")
        email = result_data.get("email")
        bio = result_data.get("bio")
        categories = result_data.get("categories") or []

        # Build rich markdown description
        desc_parts = []
        if handle:
            desc_parts.append(f"**Handle:** @{handle.lstrip('@')}")
        if platform and platform != "unknown":
            desc_parts.append(f"**Platform:** {platform.title()}")
        if profile_url:
            desc_parts.append(f"**Profile:** {profile_url}")
        if followers:
            desc_parts.append(f"**Followers:** {followers:,}")
        if score is not None:
            desc_parts.append(f"**AI Relevance Score:** {score}/100")
        if bio:
            desc_parts.append(f"**Bio:** {bio}")

        # AI analysis fields
        if ai.get("content_fit"):
            desc_parts.append(f"**Content Fit:** {ai['content_fit']}")
        if ai.get("credential_tier"):
            desc_parts.append(f"**Credential Tier:** {ai['credential_tier']}")
        if ai.get("medical_specialty"):
            desc_parts.append(f"**Specialty:** {ai['medical_specialty']}")
        if ai.get("credentials"):
            desc_parts.append(f"**Credentials:** {', '.join(ai['credentials'])}")
        if ai.get("content_niches"):
            desc_parts.append(f"**Niches:** {', '.join(ai['content_niches'])}")
        if ai.get("creator_type"):
            desc_parts.append(f"**Creator Type:** {ai['creator_type']}")
        if ai.get("estimated_rate"):
            desc_parts.append(f"**Est. Rate:** {ai['estimated_rate']}")
        if ai.get("country"):
            desc_parts.append(f"**Country:** {ai['country']}")
        if ai.get("red_flags"):
            desc_parts.append(f"**Red Flags:** {', '.join(ai['red_flags'])}")
        if ai.get("recommended_action"):
            desc_parts.append(f"**Recommended Action:** {ai['recommended_action']}")
        if ai.get("past_partnerships"):
            desc_parts.append(f"**Past Partnerships:** {', '.join(ai['past_partnerships'])}")

        # Other profiles
        other = ai.get("other_profiles") or {}
        for plat, h in other.items():
            if h:
                desc_parts.append(f"**{plat.title()}:** @{h.lstrip('@')}")

        desc_parts.append(f"\n---\n*Added via Creator Discovery Engine*")

        # Build custom fields
        custom_fields = []
        if email:
            custom_fields.append({
                "id": "e2b74079-1904-4eb7-bb37-4b1655484618",
                "value": email,
            })
        if categories:
            label_ids = self._map_categories_to_labels(categories)
            if label_ids:
                custom_fields.append({
                    "id": "04fc1e49-f53f-4a48-b959-50dd7f92fd2a",
                    "value": label_ids,
                })

        # Task name: "Creator Name (@handle)"
        task_name = name
        if handle:
            task_name = f"{name} (@{handle.lstrip('@')})"

        payload = {
            "name": task_name,
            "description": "\n".join(desc_parts),
            "custom_fields": custom_fields,
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/list/{CREATOR_POOL_LIST_ID}/task",
                json=payload,
            )

            if response.status_code in (200, 201):
                task_data = response.json()
                task_id = task_data.get("id")
                task_url = task_data.get("url", f"https://app.clickup.com/t/{task_id}")
                logger.info(f"[ClickUp] Pushed discovery result '{name}' to Creator Pool: {task_id}")
                return {"task_id": task_id, "task_url": task_url}
            else:
                logger.error(f"[ClickUp] Push failed: {response.status_code} {response.text}")
                return None

        except Exception as e:
            logger.error(f"[ClickUp] Push error: {e}")
            return None

    async def fetch_pipeline_creators(self) -> list[dict]:
        """
        Fetch all tasks from Creator Pool, Pipeline, and Content lists.
        Returns list of {name, handle, status, task_id, task_url} for dedup.
        """
        all_creators = []

        for list_id, list_name in [
            (CREATOR_POOL_LIST_ID, "Creator Pool"),
            (CREATOR_PIPELINE_LIST_ID, "Creator Pipeline"),
            (CREATOR_CONTENT_LIST_ID, "Creator Content"),
        ]:
            page = 0
            while True:
                try:
                    response = await self.client.get(
                        f"{self.base_url}/list/{list_id}/task",
                        params={
                            "page": page,
                            "subtasks": "false",
                            "include_closed": "true",
                        },
                    )

                    if response.status_code != 200:
                        logger.warning(f"[ClickUp] Failed to fetch {list_name}: {response.status_code}")
                        break

                    data = response.json()
                    tasks = data.get("tasks", [])
                    if not tasks:
                        break

                    for task in tasks:
                        task_name = task.get("name", "")
                        # Extract handle from task name like "Dr. Smith (@drsmith)"
                        handle = None
                        if "(@" in task_name and task_name.endswith(")"):
                            handle = task_name.split("(@")[-1].rstrip(")").lower()
                        # Also strip the handle part to get clean name
                        clean_name = task_name.split(" (@")[0] if " (@" in task_name else task_name

                        status = task.get("status", {}).get("status", "unknown")
                        task_id = task.get("id")
                        task_url = task.get("url", f"https://app.clickup.com/t/{task_id}")

                        all_creators.append({
                            "name": clean_name,
                            "handle": handle,
                            "status": status,
                            "task_id": task_id,
                            "task_url": task_url,
                            "list": list_name,
                        })

                    # ClickUp returns max 100 per page
                    if len(tasks) < 100:
                        break
                    page += 1

                except Exception as e:
                    logger.error(f"[ClickUp] Error fetching {list_name}: {e}")
                    break

        logger.info(f"[ClickUp] Fetched {len(all_creators)} creators from pipeline")
        return all_creators
