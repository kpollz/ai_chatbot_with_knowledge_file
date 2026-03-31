"""
Pydantic schemas for request/response validation

Note: SQLite is dynamically typed — TEXT columns may contain int/float values.
We use coerce_numbers_to_str to handle this gracefully.
"""

from pydantic import BaseModel
from typing import Optional, List

# Shared config: coerce numbers to str for SQLite compatibility
_response_config = {"from_attributes": True, "coerce_numbers_to_str": True}


# ---- Line ----

class LineResponse(BaseModel):
    LineID: int
    LineName: Optional[str] = None

    model_config = _response_config


# ---- Team ----

class TeamCreate(BaseModel):
    TeamName: str
    LineID: int


class TeamUpdate(BaseModel):
    TeamName: Optional[str] = None
    LineID: Optional[int] = None


class TeamResponse(BaseModel):
    TeamID: int
    TeamName: Optional[str] = None
    LineID: int

    model_config = _response_config


# ---- Machine ----

class MachineCreate(BaseModel):
    MachineName: str
    Location: Optional[str] = None
    Serial: Optional[str] = None
    TeamID: int


class MachineUpdate(BaseModel):
    MachineName: Optional[str] = None
    Location: Optional[str] = None
    Serial: Optional[str] = None
    TeamID: Optional[int] = None


class MachineResponse(BaseModel):
    MachineID: int
    MachineName: str
    Location: Optional[str] = None
    Serial: Optional[str] = None
    TeamID: int

    model_config = _response_config


# ---- Line (create) ----

class LineCreate(BaseModel):
    LineName: str


# ---- Issue ----

class IssueCreate(BaseModel):
    MachineID: int
    Date: Optional[str] = None
    start_time: Optional[str] = None
    stop_time: Optional[str] = None
    total_time: Optional[str] = None
    Week: Optional[int] = None
    Year: Optional[int] = None
    hien_tuong: Optional[str] = None    # Hiện tượng (Symptom)
    nguyen_nhan: Optional[str] = None   # Nguyên nhân (Cause)
    khac_phuc: Optional[str] = None     # Khắc phục (Solution)
    PIC: Optional[str] = None
    user_input: Optional[str] = None


class IssueUpdate(BaseModel):
    MachineID: Optional[int] = None
    Date: Optional[str] = None
    start_time: Optional[str] = None
    stop_time: Optional[str] = None
    total_time: Optional[str] = None
    Week: Optional[int] = None
    Year: Optional[int] = None
    hien_tuong: Optional[str] = None
    nguyen_nhan: Optional[str] = None
    khac_phuc: Optional[str] = None
    PIC: Optional[str] = None
    user_input: Optional[str] = None


class IssueResponse(BaseModel):
    IssueID: int
    MachineID: int
    Date: Optional[str] = None
    start_time: Optional[str] = None
    stop_time: Optional[str] = None
    total_time: Optional[str] = None
    Week: Optional[int] = None
    Year: Optional[int] = None
    hien_tuong: Optional[str] = None
    nguyen_nhan: Optional[str] = None
    khac_phuc: Optional[str] = None
    PIC: Optional[str] = None
    user_input: Optional[str] = None

    model_config = _response_config


# ---- Import (convenience for Excel row) ----

class IssueImportRequest(BaseModel):
    """Import a full Excel row — auto-creates Line/Team/Machine if not found."""
    LineName: str
    TeamName: str
    MachineName: str
    Location: Optional[str] = None
    Serial: Optional[str] = None
    Date: Optional[str] = None
    start_time: Optional[str] = None
    stop_time: Optional[str] = None
    total_time: Optional[str] = None
    Week: Optional[int] = None
    Year: Optional[int] = None
    hien_tuong: Optional[str] = None
    nguyen_nhan: Optional[str] = None
    khac_phuc: Optional[str] = None
    PIC: Optional[str] = None
    user_input: Optional[str] = None


class IssueImportResponse(BaseModel):
    """Response for import — includes what was created vs reused."""
    IssueID: int
    MachineID: int
    LineID: int
    TeamID: int
    created_line: bool
    created_team: bool
    created_machine: bool

    model_config = _response_config


class IssueSearchResult(BaseModel):
    """Response for the search endpoint — includes machine and line context"""
    IssueID: int
    MachineID: int
    Date: Optional[str] = None
    start_time: Optional[str] = None
    stop_time: Optional[str] = None
    total_time: Optional[str] = None
    hien_tuong: Optional[str] = None
    nguyen_nhan: Optional[str] = None
    khac_phuc: Optional[str] = None
    PIC: Optional[str] = None
    MachineName: Optional[str] = None
    LineName: Optional[str] = None
    Location: Optional[str] = None
    Serial: Optional[str] = None

    model_config = _response_config
