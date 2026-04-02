#!/usr/bin/env python3
"""
Migrate data from SQLite to PostgreSQL.
Usage: python migrate_sqlite_to_postgres.py <sqlite_db_path>
"""

import asyncio
import sys
from pathlib import Path

import httpx
import aiosqlite

API_URL = "http://localhost:8888"


async def migrate_sqlite_to_postgres(sqlite_path: str):
    """Read SQLite and import via API."""
    print(f"📖 Reading SQLite: {sqlite_path}")
    
    async with aiosqlite.connect(sqlite_path) as db:
        # Read all issues with joins
        async with db.execute("""
            SELECT 
                l.LineName,
                t.TeamName, 
                m.MachineName,
                m.Location,
                m.Serial,
                i.Date,
                i."Start Time",
                i."Stop Time", 
                i."Total Time",
                i.Week,
                i.Year,
                i."Hiện tượng",
                i."Nguyên nhân",
                i."Khắc phục",
                i.PIC,
                i."User Input"
            FROM Issues i
            JOIN Machines m ON i.MachineID = m.MachineID
            JOIN Teams t ON m.TeamID = t.TeamID
            JOIN Lines l ON t.LineID = l.LineID
        """) as cursor:
            rows = await cursor.fetchall()
    
    print(f"📊 Found {len(rows)} issues to migrate")
    
    # Import via API
    success = 0
    errors = 0
    duplicates = 0
    
    with httpx.Client(timeout=30) as client:
        for row in rows:
            data = {
                "LineName": row[0],
                "TeamName": row[1],
                "MachineName": row[2],
                "Location": row[3],
                "Serial": row[4],
                "Date": row[5],
                "start_time": row[6],
                "stop_time": row[7],
                "total_time": row[8],
                "Week": row[9],
                "Year": row[10],
                "hien_tuong": row[11],
                "nguyen_nhan": row[12],
                "khac_phuc": row[13],
                "PIC": row[14],
                "user_input": row[15],
            }
            
            try:
                response = client.post(f"{API_URL}/issues/import", json=data)
                if response.status_code == 201:
                    result = response.json()
                    if result.get("is_duplicate"):
                        duplicates += 1
                    else:
                        success += 1
                    print(f"✅ Migrated: {row[2]} @ {row[0]} - Issue #{result['IssueID']}")
                else:
                    print(f"❌ Failed: {response.text[:100]}")
                    errors += 1
            except Exception as e:
                print(f"❌ Error: {e}")
                errors += 1
    
    print(f"\n📊 Migration complete:")
    print(f"   Success: {success}")
    print(f"   Duplicates: {duplicates}")
    print(f"   Errors: {errors}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python migrate_sqlite_to_postgres.py <sqlite_db_path>")
        sys.exit(1)
    
    sqlite_path = sys.argv[1]
    if not Path(sqlite_path).exists():
        print(f"❌ File not found: {sqlite_path}")
        sys.exit(1)
    
    asyncio.run(migrate_sqlite_to_postgres(sqlite_path))
