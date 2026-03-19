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
    LineName: str

    model_config = _response_config


# ---- Team ----

class TeamResponse(BaseModel):
    TeamID: int
    TeamName: Optional[str] = None
    LineID: int

    model_config = _response_config


# ---- Machine ----

class MachineResponse(BaseModel):
    MachineID: int
    MachineName: str
    Location: Optional[str] = None
    Serial: Optional[str] = None
    TeamID: int

    model_config = _response_config


# ---- Issue ----

class IssueCreate(BaseModel):
    MachineID: int
    Date: Optional[str] = None
    start_time: Optional[str] = None
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
    total_time: Optional[str] = None
    Week: Optional[int] = None
    Year: Optional[int] = None
    hien_tuong: Optional[str] = None
    nguyen_nhan: Optional[str] = None
    khac_phuc: Optional[str] = None
    PIC: Optional[str] = None
    user_input: Optional[str] = None

    model_config = _response_config


class IssueSearchResult(BaseModel):
    """Response for the search endpoint — includes machine and line context"""
    IssueID: int
    MachineID: int
    Date: Optional[str] = None
    start_time: Optional[str] = None
    total_time: Optional[str] = None
    hien_tuong: Optional[str] = None
    nguyen_nhan: Optional[str] = None
    khac_phuc: Optional[str] = None
    PIC: Optional[str] = None
    MachineName: str
    LineName: str

    model_config = _response_config
