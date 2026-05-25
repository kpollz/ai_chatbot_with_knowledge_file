#!/usr/bin/env python3
"""
One-time migration script: rename Vietnamese columns to English in PostgreSQL.

Run this AFTER deploying the new code that uses English field names.

Usage:
    cd issue-api && python scripts/migrate_rename_columns.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent dir so we can import config
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from config import DATABASE_URL


async def migrate():
    try:
        import asyncpg
    except ImportError:
        print("❌ asyncpg not installed. Install it first: pip install asyncpg")
        sys.exit(1)

    # Convert SQLAlchemy DSN to asyncpg DSN
    dsn = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(dsn)
    try:
        print(f"🔌 Connected to database")
        print(f"📝 Renaming columns...")

        await conn.execute('ALTER TABLE issues RENAME COLUMN hien_tuong TO symptom')
        print("   ✅ hien_tuong → symptom")

        await conn.execute('ALTER TABLE issues RENAME COLUMN nguyen_nhan TO cause')
        print("   ✅ nguyen_nhan → cause")

        await conn.execute('ALTER TABLE issues RENAME COLUMN khac_phuc TO solution')
        print("   ✅ khac_phuc → solution")

        # Rename index if it exists (PostgreSQL specific)
        try:
            await conn.execute(
                "ALTER INDEX IF EXISTS idx_issues_machine_hien_tuong RENAME TO idx_issues_machine_symptom"
            )
            print("   ✅ idx_issues_machine_hien_tuong → idx_issues_machine_symptom")
        except Exception as e:
            print(f"   ⚠️ Could not rename index (may not exist): {e}")

        print("\n🎉 Migration completed successfully!")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
