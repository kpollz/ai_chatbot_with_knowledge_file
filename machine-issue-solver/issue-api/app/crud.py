"""
Async CRUD operations for PostgreSQL Issue API
"""

from typing import Optional, Tuple, List, Any
from datetime import datetime
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from models import Issue, Machine, Line, Team
from schemas import IssueCreate, IssueUpdate, IssueImportRequest


# Helper: Get next ID (not needed for PostgreSQL SERIAL, but kept for compatibility)
async def _get_next_id(db: AsyncSession, model_class) -> int:
    """Get next available ID (for PostgreSQL compatibility - SERIAL handles this)."""
    result = await db.execute(select(func.coalesce(func.max(model_class.id), 0) + 1))
    return result.scalar()


# ---- Team ----

async def get_teams(db: AsyncSession) -> List[Team]:
    result = await db.execute(select(Team).order_by(Team.id))
    return result.scalars().all()


async def get_team(db: AsyncSession, team_id: int) -> Optional[Team]:
    result = await db.execute(select(Team).where(Team.id == team_id))
    return result.scalar_one_or_none()


async def find_team_by_name(db: AsyncSession, team_name: str) -> Optional[Team]:
    """Find a team by its name (case-insensitive). Returns None if not found."""
    result = await db.execute(
        select(Team).where(func.lower(Team.name) == func.lower(team_name))
    )
    return result.scalars().first()


async def create_team(db: AsyncSession, team_name: str) -> Team:
    """Create a new team and return it."""
    db_team = Team(name=team_name)
    db.add(db_team)
    await db.commit()
    await db.refresh(db_team)
    return db_team


# ---- Line ----

async def get_lines(db: AsyncSession) -> List[Line]:
    result = await db.execute(select(Line).order_by(Line.id))
    return result.scalars().all()


async def get_line(db: AsyncSession, line_id: int) -> Optional[Line]:
    result = await db.execute(select(Line).where(Line.id == line_id))
    return result.scalar_one_or_none()


async def find_line_by_name(db: AsyncSession, line_name: str) -> Optional[Line]:
    """Find a line by its name (case-insensitive). Returns None if not found."""
    result = await db.execute(
        select(Line).where(func.lower(Line.name) == func.lower(line_name))
    )
    return result.scalars().first()


async def find_line_by_name_and_team(db: AsyncSession, line_name: str, team_id: int) -> Optional[Line]:
    """Find a line by name within a specific team. Returns None if not found."""
    result = await db.execute(
        select(Line).where(
            func.lower(Line.name) == func.lower(line_name),
            Line.team_id == team_id
        )
    )
    return result.scalars().first()


async def create_line(db: AsyncSession, line_name: str, team_id: int) -> Line:
    """Create a new line and return it."""
    db_line = Line(name=line_name, team_id=team_id)
    db.add(db_line)
    await db.commit()
    await db.refresh(db_line)
    return db_line


async def update_team(db: AsyncSession, team_id: int, team_data) -> Optional[Team]:
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


async def delete_team(db: AsyncSession, team_id: int) -> bool:
    db_team = await get_team(db, team_id)
    if not db_team:
        return False
    await db.delete(db_team)
    await db.commit()
    return True


# ---- Line Update/Delete ----

async def update_line(db: AsyncSession, line_id: int, line_data) -> Optional[Line]:
    """Update a line's fields."""
    db_line = await get_line(db, line_id)
    if not db_line:
        return None
    update_data = line_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_line, key, value)
    await db.commit()
    await db.refresh(db_line)
    return db_line


async def delete_line(db: AsyncSession, line_id: int) -> bool:
    db_line = await get_line(db, line_id)
    if not db_line:
        return False
    await db.delete(db_line)
    await db.commit()
    return True


# ---- Machine Update/Delete ----

async def update_machine(db: AsyncSession, machine_id: int, machine_data) -> Optional[Machine]:
    """Update a machine's fields."""
    db_machine = await get_machine(db, machine_id)
    if not db_machine:
        return None
    update_data = machine_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_machine, key, value)
    await db.commit()
    await db.refresh(db_machine)
    return db_machine


async def delete_machine(db: AsyncSession, machine_id: int) -> bool:
    db_machine = await get_machine(db, machine_id)
    if not db_machine:
        return False
    await db.delete(db_machine)
    await db.commit()
    return True


# ---- Machine ----

async def get_machines(db: AsyncSession) -> List[Machine]:
    result = await db.execute(select(Machine).order_by(Machine.id))
    return result.scalars().all()


async def get_machine(db: AsyncSession, machine_id: int) -> Optional[Machine]:
    result = await db.execute(select(Machine).where(Machine.id == machine_id))
    return result.scalar_one_or_none()


async def find_machine_by_details(
    db: AsyncSession, 
    machine_name: str, 
    line_id: int,
    location: Optional[str] = None, 
    serial: Optional[str] = None
) -> List[Machine]:
    """
    Find machines by name within a line, optionally filtering by location/serial.
    
    If location and serial are None: returns ALL machines with same name in line
    (useful when you want to see all variants: with/without location/serial)
    
    If location/serial provided: filters accordingly.
    Returns list of matching machines (empty list if none found).
    """
    stmt = select(Machine).where(
        func.lower(Machine.name) == func.lower(machine_name),
        Machine.line_id == line_id,
    )
    
    # Filter by location only if explicitly provided
    if location is not None:
        if location == "":
            stmt = stmt.where(Machine.location.is_(None) | (Machine.location == ""))
        else:
            stmt = stmt.where(func.lower(Machine.location) == func.lower(location))
    
    # Filter by serial only if explicitly provided
    if serial is not None:
        if serial == "":
            stmt = stmt.where(Machine.serial.is_(None) | (Machine.serial == ""))
        else:
            stmt = stmt.where(func.lower(Machine.serial) == func.lower(serial))
    
    result = await db.execute(stmt)
    return result.scalars().all()


async def create_machine(
    db: AsyncSession, 
    machine_name: str, 
    line_id: int,
    location: Optional[str] = None, 
    serial: Optional[str] = None
) -> Machine:
    """Create a new machine and return it."""
    db_machine = Machine(
        name=machine_name,
        line_id=line_id,
        location=location if location else None,
        serial=serial if serial else None,
    )
    db.add(db_machine)
    await db.commit()
    await db.refresh(db_machine)
    return db_machine


# ---- Issue ----

async def get_issues(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Issue]:
    result = await db.execute(
        select(Issue).order_by(desc(Issue.id)).offset(skip).limit(limit)
    )
    return result.scalars().all()


async def get_issue(db: AsyncSession, issue_id: int) -> Optional[Issue]:
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    return result.scalar_one_or_none()


async def search_issues(
    db: AsyncSession,
    machine_name: str,
    line_name: str,
    location: Optional[str] = None,
    serial: Optional[str] = None,
) -> List[Tuple[Any, ...]]:
    """
    Search issues by machine name and line name, with optional location and serial filters.
    Returns list of tuples: (Issue, machine_name, line_name, location, serial).
    """
    stmt = (
        select(Issue, Machine.name, Line.name, Machine.location, Machine.serial)
        .join(Machine, Issue.machine_id == Machine.id)
        .join(Line, Machine.line_id == Line.id)
        .where(func.lower(Machine.name) == func.lower(machine_name))
        .where(func.lower(Line.name) == func.lower(line_name))
    )

    # Optional filters — only applied when provided
    if location is not None:
        if location == "":
            stmt = stmt.where(Machine.location.is_(None) | (Machine.location == ""))
        else:
            stmt = stmt.where(func.lower(Machine.location) == func.lower(location))
    
    if serial is not None:
        if serial == "":
            stmt = stmt.where(Machine.serial.is_(None) | (Machine.serial == ""))
        else:
            stmt = stmt.where(func.lower(Machine.serial) == func.lower(serial))

    result = await db.execute(stmt)
    return result.all()


async def create_issue(db: AsyncSession, issue: IssueCreate) -> Issue:
    db_issue = Issue(**issue.model_dump())
    db.add(db_issue)
    await db.commit()
    await db.refresh(db_issue)
    return db_issue


async def find_existing_issue(
    db: AsyncSession, 
    machine_id: int, 
    hien_tuong: Optional[str]
) -> Optional[Issue]:
    """Check if an issue with same machine and symptom already exists."""
    if not hien_tuong:
        return None
    result = await db.execute(
        select(Issue).where(
            Issue.machine_id == machine_id,
            func.lower(Issue.hien_tuong) == func.lower(hien_tuong)
        )
    )
    return result.scalars().first()


async def import_issue(
    db: AsyncSession, 
    data: IssueImportRequest
) -> Tuple[Issue, Team, Line, Machine, bool, bool, bool, bool]:
    """
    Import a full Excel row: auto-create Team → Line → Machine if not found,
    then create the Issue. Returns (Issue, team, line, machine, created_team, created_line, created_machine, is_duplicate).
    """
    created_team = False
    created_line = False
    created_machine = False
    is_duplicate = False

    # 1. Find or create Team
    team = await find_team_by_name(db, data.team_name)
    if not team:
        team = await create_team(db, data.team_name)
        created_team = True

    # 2. Find or create Line (within team)
    line = await find_line_by_name_and_team(db, data.line_name, team.id)
    if not line:
        line = await create_line(db, data.line_name, team.id)
        created_line = True

    # 3. Find or create Machine (within line)
    machines = await find_machine_by_details(
        db, data.machine_name, line.id,
        location=data.location, serial=data.serial,
    )
    machine = machines[0] if machines else None
    if not machine:
        machine = await create_machine(
            db, data.machine_name, line.id,
            location=data.location, serial=data.serial,
        )
        created_machine = True

    # 4. Check for duplicate issue (same machine + same symptom)
    existing_issue = await find_existing_issue(db, machine.id, data.hien_tuong)
    if existing_issue:
        is_duplicate = True
        return existing_issue, team, line, machine, created_team, created_line, created_machine, is_duplicate

    # 5. Create Issue
    # Convert date string to date object if provided
    date_obj = None
    if data.date:
        try:
            date_obj = datetime.strptime(data.date, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    issue_data = {
        "machine_id": machine.id,
        "date": date_obj,
        "start_time": data.start_time,
        "stop_time": data.stop_time,
        "total_time": data.total_time,
        "week": data.week,
        "year": data.year,
        "hien_tuong": data.hien_tuong,
        "nguyen_nhan": data.nguyen_nhan,
        "khac_phuc": data.khac_phuc,
        "pic": data.pic,
        "user_input": data.user_input,
    }
    db_issue = Issue(**issue_data)
    db.add(db_issue)
    await db.commit()
    await db.refresh(db_issue)

    return db_issue, team, line, machine, created_team, created_line, created_machine, is_duplicate


async def update_issue(db: AsyncSession, issue_id: int, issue: IssueUpdate) -> Optional[Issue]:
    db_issue = await get_issue(db, issue_id)
    if not db_issue:
        return None
    update_data = issue.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_issue, key, value)
    await db.commit()
    await db.refresh(db_issue)
    return db_issue


async def delete_issue(db: AsyncSession, issue_id: int) -> bool:
    db_issue = await get_issue(db, issue_id)
    if not db_issue:
        return False
    await db.delete(db_issue)
    await db.commit()
    return True
