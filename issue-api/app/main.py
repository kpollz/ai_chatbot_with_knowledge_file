"""
FastAPI entry point for Issue API (PostgreSQL)
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import API_HOST, API_PORT
from database import init_db, check_db_connection
from routes import issue_router, line_router, machine_router, team_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    print("🔌 Checking database connection...")
    if await check_db_connection():
        print("✅ Database connected")
        # Safety check: only init if tables don't exist
        from sqlalchemy import text
        from database import async_session
        async with async_session() as session:
            try:
                result = await session.execute(
                    text("SELECT 1 FROM information_schema.tables WHERE table_name='issues'")
                )
                has_tables = result.scalar() is not None
            except Exception:
                has_tables = False
        
        if not has_tables:
            print("📊 Creating database tables (first run)...")
            await init_db()
            print("✅ Tables created")
        else:
            print("📊 Tables already exist, skipping init")
    else:
        print("❌ Database connection failed")
    yield
    # Shutdown
    print("👋 Shutting down...")


app = FastAPI(
    title="Machine Issue API",
    description="CRUD API for machine issues with PostgreSQL",
    version="2.0.0",
    lifespan=lifespan,
)

# Allow Streamlit (or any local client) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(team_router)
app.include_router(line_router)
app.include_router(machine_router)
app.include_router(issue_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "database": "postgresql"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
