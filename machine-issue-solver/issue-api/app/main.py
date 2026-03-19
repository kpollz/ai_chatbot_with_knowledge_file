"""
FastAPI entry point for Issue API
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import API_HOST, API_PORT
from routes import issue_router, line_router, machine_router

app = FastAPI(
    title="Machine Issue API",
    description="CRUD API for machine issues, lines, and machines",
    version="1.0.0",
)

# Allow Streamlit (or any local client) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(line_router)
app.include_router(machine_router)
app.include_router(issue_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
