#!/usr/bin/env python3
"""
Creator Discovery Engine — Setup & Seed Script

Run this after initial deployment to:
1. Create database tables
2. Seed default email templates
3. Verify integrations
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine, Base, async_session_factory
from app.models.models import EmailTemplate
from app.services.gmail_service import DEFAULT_TEMPLATES
from app.core.config import get_settings


async def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Tables created")


async def seed_templates():
    """Seed default email templates."""
    print("Seeding email templates...")
    async with async_session_factory() as db:
        for tmpl_data in DEFAULT_TEMPLATES:
            template = EmailTemplate(**tmpl_data)
            db.add(template)

        await db.commit()
        print(f"✓ {len(DEFAULT_TEMPLATES)} templates seeded")


async def verify_config():
    """Check that required config is present."""
    settings = get_settings()
    checks = {
        "Database URL": bool(settings.database_url),
        "Anthropic API Key": bool(settings.anthropic_api_key),
        "ClickUp API Token": bool(settings.clickup_api_token),
        "Google Client ID": bool(settings.google_client_id),
        "Google Client Secret": bool(settings.google_client_secret),
    }

    print("\nConfiguration check:")
    for name, ok in checks.items():
        status = "✓" if ok else "✗ MISSING"
        print(f"  {status} {name}")

    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        print(f"\n⚠ {len(missing)} config items missing. Set them in .env")
        print("  The app will still run, but some features will be disabled.")
    else:
        print("\n✓ All configuration present")


async def main():
    print("=" * 50)
    print("Creator Discovery Engine — Setup")
    print("=" * 50)
    print()

    await create_tables()
    await seed_templates()
    await verify_config()

    print()
    print("=" * 50)
    print("Setup complete!")
    print()
    print("Start the server with:")
    print("  uvicorn app.main:app --reload")
    print()
    print("API docs available at:")
    print("  http://localhost:8000/docs")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
