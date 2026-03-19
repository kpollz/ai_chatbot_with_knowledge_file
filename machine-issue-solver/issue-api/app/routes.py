"""
REST endpoint definitions for Issue API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from database import get_db
from schemas import (
    LineResponse,
    MachineResponse,
    IssueCreate,
    IssueUpdate,
    IssueResponse,
    IssueSearchResult,
)
import crud


# ---- Lines (read-only) ----

line_router = APIRouter(prefix="/lines", tags=["lines"])


@line_router.get("/", response_model=List[LineResponse])
async def list_lines(db: AsyncSession = Depends(get_db)):
    return await crud.get_lines(db)


@line_router.get("/{line_id}", response_model=LineResponse)
async def get_line(line_id: int, db: AsyncSession = Depends(get_db)):
    line = await crud.get_line(db, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    return line


# ---- Machines (read-only) ----

machine_router = APIRouter(prefix="/machines", tags=["machines"])


@machine_router.get("/", response_model=List[MachineResponse])
async def list_machines(db: AsyncSession = Depends(get_db)):
    return await crud.get_machines(db)


@machine_router.get("/{machine_id}", response_model=MachineResponse)
async def get_machine(machine_id: int, db: AsyncSession = Depends(get_db)):
    machine = await crud.get_machine(db, machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    return machine


# ---- Issues (full CRUD) ----

issue_router = APIRouter(prefix="/issues", tags=["issues"])


@issue_router.get("/", response_model=List[IssueResponse])
async def list_issues(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await crud.get_issues(db, skip=skip, limit=limit)


@issue_router.get("/search", response_model=List[IssueSearchResult])
async def search_issues(
    machine_name: str = Query(..., description="Machine name to search"),
    line_name: str = Query(..., description="Line name to search"),
    db: AsyncSession = Depends(get_db),
):
    """Search issues by machine name and line name — used by the chatbot."""
    rows = await crud.search_issues(db, machine_name, line_name)
    return [
        IssueSearchResult(
            IssueID=issue.IssueID,
            MachineID=issue.MachineID,
            Date=issue.Date,
            start_time=issue.start_time,
            total_time=issue.total_time,
            hien_tuong=issue.hien_tuong,
            nguyen_nhan=issue.nguyen_nhan,
            khac_phuc=issue.khac_phuc,
            PIC=issue.PIC,
            MachineName=machine_name_val,
            LineName=line_name_val,
        )
        for issue, machine_name_val, line_name_val in rows
    ]


@issue_router.get("/{issue_id}", response_model=IssueResponse)
async def get_issue(issue_id: int, db: AsyncSession = Depends(get_db)):
    issue = await crud.get_issue(db, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@issue_router.post("/", response_model=IssueResponse, status_code=201)
async def create_issue(issue: IssueCreate, db: AsyncSession = Depends(get_db)):
    return await crud.create_issue(db, issue)


@issue_router.put("/{issue_id}", response_model=IssueResponse)
async def update_issue(
    issue_id: int, issue: IssueUpdate, db: AsyncSession = Depends(get_db)
):
    updated = await crud.update_issue(db, issue_id, issue)
    if not updated:
        raise HTTPException(status_code=404, detail="Issue not found")
    return updated


@issue_router.delete("/{issue_id}", status_code=204)
async def delete_issue(issue_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await crud.delete_issue(db, issue_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Issue not found")
