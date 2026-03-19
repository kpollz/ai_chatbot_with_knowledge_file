"""
Async CRUD operations for Issue API
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Issue, Machine, Team, Line
from schemas import IssueCreate, IssueUpdate


# ---- Line (read-only) ----

async def get_lines(db: AsyncSession):
    result = await db.execute(select(Line).order_by(Line.LineID))
    return result.scalars().all()


async def get_line(db: AsyncSession, line_id: int):
    result = await db.execute(select(Line).where(Line.LineID == line_id))
    return result.scalar_one_or_none()


# ---- Machine (read-only) ----

async def get_machines(db: AsyncSession):
    result = await db.execute(select(Machine).order_by(Machine.MachineID))
    return result.scalars().all()


async def get_machine(db: AsyncSession, machine_id: int):
    result = await db.execute(select(Machine).where(Machine.MachineID == machine_id))
    return result.scalar_one_or_none()


# ---- Issue (full CRUD) ----

async def get_issues(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(
        select(Issue).order_by(Issue.IssueID).offset(skip).limit(limit)
    )
    return result.scalars().all()


async def get_issue(db: AsyncSession, issue_id: int):
    result = await db.execute(select(Issue).where(Issue.IssueID == issue_id))
    return result.scalar_one_or_none()


async def search_issues(db: AsyncSession, machine_name: str, line_name: str):
    """
    Search issues by machine name and line name.
    This is the key query used by the chatbot.
    Returns list of (Issue, MachineName, LineName) tuples.
    """
    stmt = (
        select(Issue, Machine.MachineName, Line.LineName)
        .join(Machine, Issue.MachineID == Machine.MachineID)
        .join(Team, Machine.TeamID == Team.TeamID)
        .join(Line, Team.LineID == Line.LineID)
        .where(Machine.MachineName == machine_name)
        .where(Line.LineName == line_name)
    )
    result = await db.execute(stmt)
    return result.all()


async def create_issue(db: AsyncSession, issue: IssueCreate):
    db_issue = Issue(**issue.model_dump())
    db.add(db_issue)
    await db.commit()
    await db.refresh(db_issue)
    return db_issue


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
