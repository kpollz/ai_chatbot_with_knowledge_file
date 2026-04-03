"""
REST endpoint definitions for Issue API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from database import get_db
from schemas import (
    TeamResponse,
    TeamCreate,
    LineResponse,
    LineCreate,
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
    existing = await crud.find_team_by_name(db, team.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Team '{team.name}' already exists")
    return await crud.create_team(db, team.name)


@team_router.get("/find/by-name", response_model=TeamResponse)
async def find_team_by_name(
    team_name: str = Query(..., description="Team name to find"),
    db: AsyncSession = Depends(get_db),
):
    """Find a team by name. Returns 404 if not found."""
    team = await crud.find_team_by_name(db, team_name)
    if not team:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found")
    return team


@team_router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: int, team: TeamCreate, db: AsyncSession = Depends(get_db)
):
    """Update a team's name."""
    updated = await crud.update_team(db, team_id, team)
    if not updated:
        raise HTTPException(status_code=404, detail="Team not found")
    return updated


@team_router.delete("/{team_id}", status_code=204)
async def delete_team(team_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a team and all its lines/machines/issues."""
    deleted = await crud.delete_team(db, team_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Team not found")


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
    raise HTTPException(
        status_code=400, 
        detail="Please use /issues/import endpoint or create line with team_id"
    )


@line_router.get("/find/by-name", response_model=LineResponse)
async def find_line_by_name(
    line_name: str = Query(..., description="Line name to find"),
    team_id: int = Query(..., description="Team ID to search within"),
    db: AsyncSession = Depends(get_db),
):
    """Find a line by name within a specific team."""
    line = await crud.find_line_by_name_and_team(db, line_name, team_id)
    if not line:
        raise HTTPException(status_code=404, detail=f"Line '{line_name}' not found in team {team_id}")
    return line


@line_router.put("/{line_id}", response_model=LineResponse)
async def update_line(
    line_id: int, line: LineCreate, db: AsyncSession = Depends(get_db)
):
    """Update a line's name."""
    updated = await crud.update_line(db, line_id, line)
    if not updated:
        raise HTTPException(status_code=404, detail="Line not found")
    return updated


@line_router.delete("/{line_id}", status_code=204)
async def delete_line(line_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a line and all its machines/issues."""
    deleted = await crud.delete_line(db, line_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Line not found")


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
        db, machine.name, machine.line_id,
        location=machine.location, serial=machine.serial,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Machine already exists")
    return await crud.create_machine(
        db, machine.name, machine.line_id,
        location=machine.location, serial=machine.serial,
    )


@machine_router.get("/find/by-details", response_model=List[MachineResponse])
async def find_machine_by_details(
    machine_name: str = Query(..., description="Machine name"),
    line_id: int = Query(..., description="Line ID"),
    location: str = Query(None, description="Optional location filter"),
    serial: str = Query(None, description="Optional serial filter"),
    db: AsyncSession = Depends(get_db),
):
    """
    Find machines by name within a line.
    
    - If location and serial are provided: returns specific machine
    - If only name + line_id: returns ALL machines with that name in the line
      (including variants with/without location/serial)
    """
    machines = await crud.find_machine_by_details(
        db, machine_name, line_id, location=location, serial=serial,
    )
    if not machines:
        raise HTTPException(status_code=404, detail="No machines found")
    return machines


@machine_router.put("/{machine_id}", response_model=MachineResponse)
async def update_machine(
    machine_id: int, machine: MachineUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a machine's fields."""
    updated = await crud.update_machine(db, machine_id, machine)
    if not updated:
        raise HTTPException(status_code=404, detail="Machine not found")
    return updated


@machine_router.delete("/{machine_id}", status_code=204)
async def delete_machine(machine_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a machine and all its issues."""
    deleted = await crud.delete_machine(db, machine_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Machine not found")


# ---- Issues (full CRUD) ----

issue_router = APIRouter(prefix="/issues", tags=["issues"])


@issue_router.get("/", response_model=List[IssueResponse])
async def list_issues(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    issues = await crud.get_issues(db, skip=skip, limit=limit)
    # Convert date to string format
    for issue in issues:
        if issue.date and hasattr(issue.date, 'strftime'):
            issue.date = issue.date.strftime("%Y-%m-%d")
    return issues


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
            IssueID=issue.id,
            MachineID=issue.machine_id,
            Date=issue.date.strftime("%Y-%m-%d") if issue.date else None,
            start_time=issue.start_time,
            stop_time=issue.stop_time,
            total_time=issue.total_time,
            hien_tuong=issue.hien_tuong,
            nguyen_nhan=issue.nguyen_nhan,
            khac_phuc=issue.khac_phuc,
            PIC=issue.pic,
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
    Import a full Excel row — auto-creates Team, Line, Machine if not found.
    If an issue with the same machine and symptom (hien_tuong) already exists,
    returns the existing issue with is_duplicate=True.
    """
    issue, team, line, machine, created_team, created_line, created_machine, is_duplicate = (
        await crud.import_issue(db, data)
    )
    
    return IssueImportResponse(
        IssueID=issue.id,
        MachineID=machine.id,
        LineID=line.id,
        TeamID=team.id,
        created_team=created_team,
        created_line=created_line,
        created_machine=created_machine,
        is_duplicate=is_duplicate,
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
