"""
REST endpoint definitions for Issue API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from database import get_db
from schemas import (
    LineResponse,
    LineCreate,
    TeamCreate,
    TeamUpdate,
    TeamResponse,
    MachineCreate,
    MachineUpdate,
    MachineResponse,
    IssueCreate,
    IssueUpdate,
    IssueResponse,
    IssueSearchResult,
    IssueImportRequest,
    IssueImportResponse,
)
import crud


# ---- Lines ----

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


@line_router.post("/", response_model=LineResponse, status_code=201)
async def create_line(line: LineCreate, db: AsyncSession = Depends(get_db)):
    existing = await crud.find_line_by_name(db, line.LineName)
    if existing:
        raise HTTPException(status_code=409, detail=f"Line '{line.LineName}' already exists")
    return await crud.create_line(db, line.LineName)


@line_router.get("/find/by-name", response_model=LineResponse)
async def find_line_by_name(
    line_name: str = Query(..., description="Line name to find"),
    db: AsyncSession = Depends(get_db),
):
    """Find a line by name. Returns 404 if not found."""
    line = await crud.find_line_by_name(db, line_name)
    if not line:
        raise HTTPException(status_code=404, detail=f"Line '{line_name}' not found")
    return line


# ---- Teams ----

team_router = APIRouter(prefix="/teams", tags=["teams"])


@team_router.get("/", response_model=List[TeamResponse])
async def list_teams(db: AsyncSession = Depends(get_db)):
    return await crud.get_teams(db)


@team_router.get("/{team_id}", response_model=TeamResponse)
async def get_team(team_id: int, db: AsyncSession = Depends(get_db)):
    team = await crud.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@team_router.post("/", response_model=TeamResponse, status_code=201)
async def create_team(team: TeamCreate, db: AsyncSession = Depends(get_db)):
    existing = await crud.find_team_by_name(db, team.TeamName, team.LineID)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Team '{team.TeamName}' already exists in this line",
        )
    return await crud.create_team(db, team.TeamName, team.LineID)


@team_router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int, team: TeamUpdate, db: AsyncSession = Depends(get_db)
):
    updated = await crud.update_team(db, team_id, team)
    if not updated:
        raise HTTPException(status_code=404, detail="Team not found")
    return updated


@team_router.delete("/{team_id}", status_code=204)
async def delete_team(team_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await crud.delete_team(db, team_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Team not found")


@team_router.get("/find/by-name", response_model=TeamResponse)
async def find_team_by_name(
    team_name: str = Query(..., description="Team name"),
    line_id: int = Query(..., description="Line ID to search within"),
    db: AsyncSession = Depends(get_db),
):
    """Find a team by name within a specific line."""
    team = await crud.find_team_by_name(db, team_name, line_id)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found in line {line_id}")
    return team


# ---- Machines ----

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


@machine_router.post("/", response_model=MachineResponse, status_code=201)
async def create_machine(machine: MachineCreate, db: AsyncSession = Depends(get_db)):
    existing = await crud.find_machine_by_details(
        db, machine.MachineName, machine.TeamID,
        location=machine.Location, serial=machine.Serial,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Machine already exists")
    return await crud.create_machine(
        db, machine.MachineName, machine.TeamID,
        location=machine.Location, serial=machine.Serial,
    )


@machine_router.get("/find/by-details", response_model=MachineResponse)
async def find_machine_by_details(
    machine_name: str = Query(..., description="Machine name"),
    team_id: int = Query(..., description="Team ID"),
    location: str = Query(None, description="Optional location filter"),
    serial: str = Query(None, description="Optional serial filter"),
    db: AsyncSession = Depends(get_db),
):
    """Find a machine by name within a team, optionally filtered by location/serial."""
    machine = await crud.find_machine_by_details(
        db, machine_name, team_id, location=location, serial=serial,
    )
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
    location: str = Query(None, description="Optional machine location filter"),
    serial: str = Query(None, description="Optional machine serial filter"),
    db: AsyncSession = Depends(get_db),
):
    """Search issues by machine name and line name, with optional location and serial filters — used by the chatbot."""
    rows = await crud.search_issues(db, machine_name, line_name, location=location, serial=serial)
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
            Location=location_val,
            Serial=serial_val,
        )
        for issue, machine_name_val, line_name_val, location_val, serial_val in rows
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


@issue_router.post("/import", response_model=IssueImportResponse, status_code=201)
async def import_issue(data: IssueImportRequest, db: AsyncSession = Depends(get_db)):
    """
    Import a full Excel row — auto-creates Line, Team, Machine if not found.
    This is the primary endpoint for bulk data import from Excel files.
    """
    issue, line, team, machine, created_line, created_team, created_machine = (
        await crud.import_issue(db, data)
    )
    return IssueImportResponse(
        IssueID=issue.IssueID,
        MachineID=machine.MachineID,
        LineID=line.LineID,
        TeamID=team.TeamID,
        created_line=created_line,
        created_team=created_team,
        created_machine=created_machine,
    )


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
