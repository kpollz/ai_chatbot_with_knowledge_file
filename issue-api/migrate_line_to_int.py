#!/usr/bin/env python3
"""
Migration script: Convert lines.name (str) to lines.line_number (int)
Usage: python migrate_line_to_int.py
"""

import asyncio
import re
import asyncpg
from config import DATABASE_URL

# Remove asyncpg+ prefix for direct connection
DB_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def migrate():
    print("🔌 Connecting to database...")
    conn = await asyncpg.connect(DB_URL)
    
    try:
        # 1. Check if migration already done
        cols = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'lines'
        """)
        col_names = [c['column_name'] for c in cols]
        
        if 'line_number' in col_names and 'name' not in col_names:
            print("✅ Migration already completed (line_number exists, name removed)")
            return
        
        if 'line_number' not in col_names:
            print("📊 Step 1: Adding line_number column...")
            await conn.execute("ALTER TABLE lines ADD COLUMN line_number INTEGER")
        
        # 2. Convert data
        print("📊 Step 2: Converting name to line_number...")
        rows = await conn.fetch("SELECT id, name FROM lines")
        
        for row in rows:
            line_id = row['id']
            name = row['name']
            
            # Parse "Line 2", "02", "2" -> 2
            try:
                if isinstance(name, int):
                    line_num = name
                else:
                    # Remove non-digits and convert
                    num_str = re.sub(r'[^0-9]', '', str(name))
                    line_num = int(num_str) if num_str else None
                
                if line_num:
                    await conn.execute(
                        "UPDATE lines SET line_number = $1 WHERE id = $2",
                        line_num, line_id
                    )
                    print(f"   Line {line_id}: '{name}' -> {line_num}")
            except Exception as e:
                print(f"   ⚠️  Line {line_id}: '{name}' failed - {e}")
        
        # 3. Check for nulls
        null_count = await conn.fetchval(
            "SELECT COUNT(*) FROM lines WHERE line_number IS NULL"
        )
        if null_count > 0:
            print(f"⚠️  Warning: {null_count} rows have NULL line_number")
        
        # 4. Drop old column
        if 'name' in col_names:
            print("📊 Step 3: Dropping old 'name' column...")
            await conn.execute("ALTER TABLE lines DROP COLUMN name")
        
        # 5. Add constraint
        print("📊 Step 4: Adding NOT NULL constraint...")
        await conn.execute("""
            ALTER TABLE lines 
            ALTER COLUMN line_number SET NOT NULL
        """)
        
        print("✅ Migration completed successfully!")
        
        # Show result
        lines = await conn.fetch("SELECT id, line_number FROM lines ORDER BY line_number LIMIT 10")
        print("\nSample data:")
        for line in lines:
            print(f"   Line {line['id']}: number={line['line_number']}")
            
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
