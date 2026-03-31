"""
Async CRUD operations for Issue API
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Issue, Machine, Team, Line
from schemas import IssueCreate, IssueUpdate, IssueImportRequest


# ---- Line ----

async def get_lines(db: AsyncSession):
    result = await db.execute(select(Line).order_by(Line.LineID))
    return result.scalars().all()


async def get_line(db: AsyncSession, line_id: int):
    result = await db.execute(select(Line).where(Line.LineID == line_id))
    return result.scalar_one_or_none()


async def find_line_by_name(db: AsyncSession, line_name: str):
    """Find a line by its name. Returns None if not found."""
    result = await db.execute(select(Line).where(Line.LineName == line_name))
    return result.scalar_one_or_none()


async def create_line(db: AsyncSession, line_name: str):
    """Create a new line and return it."""
    db_line = Line(LineName=line_name)
    db.add(db_line)
    await db.commit()
    await db.refresh(db_line)
    return db_line


# ---- Team ----

async def get_teams(db: AsyncSession):
    result = await db.execute(select(Team).order_by(Team.TeamID))
    return result.scalars().all()


async def get_team(db: AsyncSession, team_id: int):
    result = await db.execute(select(Team).where(Team.TeamID == team_id))
    return result.scalar_one_or_none()


async def find_team_by_name(db: AsyncSession, team_name: str, line_id: int):
    """Find a team by name within a specific line. Returns None if not found."""
    result = await db.execute(
        select(Team).where(Team.TeamName == team_name, Team.LineID == line_id)
    )
    return result.scalar_one_or_none()


async def create_team(db: AsyncSession, team_name: str, line_id: int):
    """Create a new team and return it."""
    db_team = Team(TeamName=team_name, LineID=line_id)
    db.add(db_team)
    await db.commit()
    await db.refresh(db_team)
    return db_team


async def update_team(db: AsyncSession, team_id: int, team_data):
    """Update a team's fields."""
    db_team = await get_team(db, team_id)
    if not db_team:
        return None
    update_data = team_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_team, key, value)
    await db.commit()
    await db.refresh(db_team)
    return db_team


async def delete_team(db: AsyncSession, team_id: int):
    db_team = await get_team(db, team_id)
    if not db_team:
        return False
    await db.delete(db_team)
    await db.commit()
    return True


# ---- Machine ----

async def get_machines(db: AsyncSession):
    result = await db.execute(select(Machine).order_by(Machine.MachineID))
    return result.scalars().all()


async def get_machine(db: AsyncSession, machine_id: int):
    result = await db.execute(select(Machine).where(Machine.MachineID == machine_id))
    return result.scalar_one_or_none()


async def find_machine_by_details(db: AsyncSession, machine_name: str, team_id: int,
                                   location: str = None, serial: str = None):
    """Find a machine by name within a team, optionally filtering by location/serial.
    Returns the first match or None."""
    stmt = select(Machine).where(
        Machine.MachineName == machine_name,
        Machine.TeamID == team_id,
    )
    if location:
        stmt = stmt.where(Machine.Location == location)
    if serial:
        stmt = stmt.where(Machine.Serial == serial)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_machine(db: AsyncSession, machine_name: str, team_id: int,
                         location: str = None, serial: str = None):
    """Create a new machine and return it."""
    db_machine = Machine(MachineName=machine_name, TeamID=team_id,
                         Location=location, Serial=serial)
    db.add(db_machine)
    await db.commit()
    await db.refresh(db_machine)
    return db_machine


# ---- Issue (full CRUD) ----

async def get_issues(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(Issue).order_by(Issue.IssueID).offset(skip).limit(limit)
    )
    return result.scalars().all()


async def get_issue(db: AsyncSession, issue_id: int):
    result = await db.execute(select(Issue).where(Issue.IssueID == issue_id))
    return result.scalar_one_or_none()


async def search_issues(
    db: AsyncSession,
    machine_name: str,
    line_name: str,
    location: str = None,
    serial: str = None,
):
    """
    Search issues by machine name and line name, with optional location and serial filters.
    This is the key query used by the chatbot.
    Returns list of (Issue, MachineName, LineName, Location, Serial) tuples.
    """
    stmt = (
        select(Issue, Machine.MachineName, Line.LineName, Machine.Location, Machine.Serial)
        .join(Machine, Issue.MachineID == Machine.MachineID)
        .join(Team, Machine.TeamID == Team.TeamID)
        .join(Line, Team.LineID == Line.LineID)
        .where(Machine.MachineName == machine_name)
        .where(Line.LineName == line_name)
    )

    # Optional filters — only applied when provided
    if location:
        stmt = stmt.where(Machine.Location == location)
    if serial:
        stmt = stmt.where(Machine.Serial == serial)

    result = await db.execute(stmt)
    return result.all()


async def create_issue(db: AsyncSession, issue: IssueCreate):
    db_issue = Issue(**issue.model_dump())
    db.add(db_issue)
    await db.commit()
    await db.refresh(db_issue)
    return db_issue


async def import_issue(db: AsyncSession, data: IssueImportRequest):
    """
    Import a full Excel row: auto-create Line → Team → Machine if not found,
    then create the Issue. Returns (Issue, created_line, created_team, created_machine).
    """
    created_line = False
    created_team = False
    created_machine = False

    # 1. Find or create Line
    line = await find_line_by_name(db, data.LineName)
    if not line:
        line = await create_line(db, data.LineName)
        created_line = True

    # 2. Find or create Team
    team = await find_team_by_name(db, data.TeamName, line.LineID)
    if not team:
        team = await create_team(db, data.TeamName, line.LineID)
        created_team = True

    # 3. Find or create Machine
    machine = await find_machine_by_details(
        db, data.MachineName, team.TeamID,
        location=data.Location, serial=data.Serial,
    )
    if not machine:
        machine = await create_machine(
            db, data.MachineName, team.TeamID,
            location=data.Location, serial=data.Serial,
        )
        created_machine = True

    # 4. Create Issue
    issue_data = {
        "MachineID": machine.MachineID,
        "Date": data.Date,
        "start_time": data.start_time,
        "total_time": data.total_time,
        "Week": data.Week,
        "Year": data.Year,
        "hien_tuong": data.hien_tuong,
        "nguyen_nhan": data.nguyen_nhan,
        "khac_phuc": data.khac_phuc,
        "PIC": data.PIC,
        "user_input": data.user_input,
    }
    db_issue = Issue(**issue_data)
    db.add(db_issue)
    await db.commit()
    await db.refresh(db_issue)

    return db_issue, line, team, machine, created_line, created_team, created_machine


async def update_issue(db: AsyncSession, issue_id: int, issue: IssueUpdate):
    db_issue = await get_issue(db, issue_id)
    if not db_issue:
        return None
    update_data = issue.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_issue, key, value)
    await db.commit()
    await db.refresh(db_issue)
    return db_issue


async def delete_issue(db: AsyncSession, issue_id: int):
    db_issue = await get_issue(db, issue_id)
    if not db_issue:
        return False
    await db.delete(db_issue)
    await db.commit()
    return True
