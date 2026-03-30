"""
Gmail Integration Service

Handles sending outreach emails and tracking conversations via Gmail API.
Uses OAuth2 for authentication with the influencer coordinator's Gmail account.
"""

import base64
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import OutreachEmail, OutreachStatus, Creator, CreatorNote

logger = logging.getLogger(__name__)


class GmailService:
    """Sends and tracks outreach emails via Gmail API."""

    def __init__(self, credentials: Credentials):
        self.service = build("gmail", "v1", credentials=credentials)

    @classmethod
    def from_tokens(cls, access_token: str, refresh_token: str, client_id: str, client_secret: str):
        """Create service from OAuth tokens."""
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        return cls(creds)

    def _build_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        reply_to: Optional[str] = None,
    ) -> dict:
        """Build a Gmail-compatible email message."""
        message = MIMEMultipart("alternative")
        message["to"] = to
        message["subject"] = subject
        if from_email:
            message["from"] = from_email
        if reply_to:
            message["reply-to"] = reply_to

        # Plain text version
        text_part = MIMEText(body, "plain")
        message.attach(text_part)

        # HTML version (simple formatting)
        html_body = body.replace("\n", "<br>")
        html_part = MIMEText(f"<div style='font-family: Arial, sans-serif; font-size: 14px;'>{html_body}</div>", "html")
        message.attach(html_part)

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        return {"raw": raw}

    async def send_email(
        self,
        outreach: OutreachEmail,
        db: AsyncSession,
    ) -> bool:
        """Send an outreach email and update tracking."""
        try:
            email_msg = self._build_email(
                to=outreach.to_email,
                subject=outreach.subject,
                body=outreach.body,
                from_email=outreach.from_email,
            )

            # Send via Gmail API
            result = self.service.users().messages().send(
                userId="me", body=email_msg
            ).execute()

            # Update outreach record
            outreach.gmail_message_id = result.get("id")
            outreach.gmail_thread_id = result.get("threadId")
            outreach.status = OutreachStatus.SENT
            outreach.sent_at = datetime.utcnow()

            # Add note to creator
            note = CreatorNote(
                creator_id=outreach.creator_id,
                content=f"Outreach email sent: {outreach.subject}",
                note_type="email_sent",
            )
            db.add(note)

            await db.commit()
            logger.info(f"Email sent to {outreach.to_email}: {result.get('id')}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {outreach.to_email}: {e}")
            outreach.status = OutreachStatus.BOUNCED
            await db.commit()
            return False

    async def check_replies(
        self,
        outreach: OutreachEmail,
        db: AsyncSession,
    ) -> Optional[dict]:
        """Check if an outreach email has received a reply."""
        if not outreach.gmail_thread_id:
            return None

        try:
            thread = self.service.users().threads().get(
                userId="me", id=outreach.gmail_thread_id
            ).execute()

            messages = thread.get("messages", [])
            if len(messages) > 1:
                # There's a reply
                latest = messages[-1]
                headers = {h["name"]: h["value"] for h in latest.get("payload", {}).get("headers", [])}

                # Check if reply is FROM the creator (not from us)
                from_addr = headers.get("From", "")
                if outreach.to_email.lower() in from_addr.lower():
                    outreach.status = OutreachStatus.REPLIED
                    outreach.replied_at = datetime.utcnow()

                    note = CreatorNote(
                        creator_id=outreach.creator_id,
                        content=f"Creator replied to outreach: {outreach.subject}",
                        note_type="email_received",
                    )
                    db.add(note)
                    await db.commit()

                    return {
                        "replied": True,
                        "reply_from": from_addr,
                        "reply_snippet": latest.get("snippet", ""),
                    }

            return {"replied": False}

        except Exception as e:
            logger.error(f"Failed to check replies: {e}")
            return None

    async def get_thread_history(self, thread_id: str) -> list[dict]:
        """Get full email conversation history for a thread."""
        try:
            thread = self.service.users().threads().get(
                userId="me", id=thread_id, format="full"
            ).execute()

            messages = []
            for msg in thread.get("messages", []):
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                messages.append({
                    "id": msg["id"],
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", ""),
                })

            return messages

        except Exception as e:
            logger.error(f"Failed to get thread history: {e}")
            return []


# ─── EMAIL TEMPLATE ENGINE ───

def render_template(template_body: str, creator: Creator) -> str:
    """Render an email template with creator-specific variables."""
    first_name = creator.name.split()[0] if creator.name else "there"

    primary_category = creator.categories[0] if creator.categories else "wellness"
    platform = "TikTok" if creator.tiktok_url else "Instagram" if creator.instagram_url else "social media"

    replacements = {
        "{{creator_name}}": creator.name,
        "{{first_name}}": first_name,
        "{{category}}": primary_category,
        "{{platform}}": platform,
        "{{handle}}": creator.tiktok_handle or creator.instagram_handle or "",
    }

    result = template_body
    for key, value in replacements.items():
        result = result.replace(key, value or "")

    return result


# ─── DEFAULT TEMPLATES ───

DEFAULT_TEMPLATES = [
    {
        "name": "First Touch — General",
        "template_type": "first_touch",
        "subject_template": "Collaboration Opportunity — Luma Nutrition x {{creator_name}}",
        "body_template": """Hi {{first_name}},

I came across your {{platform}} content and love what you're creating — especially your focus on {{category}}. Your authentic approach really stands out.

I'm reaching out from Luma Nutrition. We're a premium supplement brand focused on Heart Health, Gut Health, and Longevity. We work with a select group of creators who genuinely care about wellness, and I think you'd be an amazing fit.

We'd love to explore a partnership where you create content featuring our products in your natural style — no scripts, just authentic integration.

Would you be open to a quick chat this week? I'd love to walk you through what we're thinking.

Best,
[Your Name]
Luma Nutrition""",
    },
    {
        "name": "First Touch — Doctor/Medical",
        "template_type": "first_touch",
        "subject_template": "Evidence-Based Supplement Brand Seeking Medical Creator Partnership",
        "body_template": """Hi {{first_name}},

I've been following your health education content on {{platform}} and really appreciate the evidence-based approach you bring to wellness topics.

I'm reaching out from Luma Nutrition. We create premium, clinically-informed supplements — our Heart Health Bundle, Gut Health Protocol, and Longevity Protocol are all formulated with ingredients backed by peer-reviewed research.

We're specifically looking to partner with medical professionals like yourself who can speak to these products with credibility and nuance. We believe health education should come from trusted voices, not just marketers.

We'd love to send you some samples and discuss a potential collaboration. No pressure to promote — we just want you to try the products and see if they align with your standards.

Would you have 15 minutes for a call this week?

Best,
[Your Name]
Luma Nutrition""",
    },
    {
        "name": "Follow-Up #1",
        "template_type": "follow_up_1",
        "subject_template": "Re: Collaboration Opportunity — Luma Nutrition x {{creator_name}}",
        "body_template": """Hi {{first_name}},

Just wanted to follow up on my previous message. I know you're busy creating great content!

We're still very interested in working with you. A few creators we've recently partnered with have seen great results — both in terms of audience engagement and the products themselves.

If you're interested, I'd love to set up a quick 10-minute call to discuss. No commitment needed.

Best,
[Your Name]
Luma Nutrition""",
    },
    {
        "name": "Follow-Up #2 — Final",
        "template_type": "follow_up_2",
        "subject_template": "Re: Collaboration Opportunity — Luma Nutrition x {{creator_name}}",
        "body_template": """Hi {{first_name}},

Last note from me — I don't want to be a pest! Just wanted to leave the door open in case the timing wasn't right before.

If you're ever interested in exploring a partnership with Luma Nutrition, we'd love to hear from you. You can reply to this email anytime.

Wishing you all the best with your content!

[Your Name]
Luma Nutrition""",
    },
]
