# Migration Guide: SQLite to PostgreSQL

## Architecture Changes

### Schema Changes

| SQLite (Old) | PostgreSQL (New) |
|--------------|------------------|
| `Lines` → `Teams` (top level) | `teams` |
| `Teams` → child of Lines | `lines` (child of teams) |
| `Machines` → child of Teams | `machines` (child of lines) |
| `Issues` → child of Machines | `issues` |

### Relationship

```
SQLite:                    PostgreSQL:
Lines                      teams
  └── Teams                  └── lines
        └── Machines               └── machines
              └── Issues                 └── issues
```

## API Compatibility

✅ **All API endpoints remain unchanged** - same URLs, same request/response format.

Field names in API remain CamelCase:
- `TeamID`, `TeamName`
- `LineID`, `LineName`  
- `MachineID`, `MachineName`, `Location`, `Serial`
- `IssueID`, `hien_tuong`, `nguyen_nhan`, etc.

## Running with Docker

```bash
# Start PostgreSQL and API
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop
docker-compose down

# Reset database (delete all data)
docker-compose down -v
docker-compose up -d
```

## Running Locally (without Docker)

```bash
# 1. Install PostgreSQL
# Mac: brew install postgresql
# Ubuntu: sudo apt-get install postgresql

# 2. Create database
createdb issue_api

# 3. Update .env
cp .env.example .env
# Edit DATABASE_URL if needed

# 4. Run API
cd app
python main.py
```

## Import Excel

The `import_excel.py` script works without changes:

```bash
python import_excel.py data.xlsx --api-url http://localhost:8888
```

## Key Improvements

1. **Concurrent writes** - Multiple imports can run simultaneously
2. **Full-text search** - Can add PostgreSQL text search later
3. **Better data integrity** - Foreign key constraints enforced
4. **Case-insensitive search** - Team/Line/Machine names matched case-insensitively
5. **Duplicate detection** - Import skips duplicate issues automatically
