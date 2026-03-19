"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel
from typing import Optional, List


# ---- Line ----

class LineResponse(BaseModel):
    LineID: int
    LineName: str

    model_config = {"from_attributes": True}


# ---- Team ----

class TeamResponse(BaseModel):
    TeamID: int
    TeamName: Optional[str] = None
    LineID: int

    model_config = {"from_attributes": True}


# ---- Machine ----

class MachineResponse(BaseModel):
    MachineID: int
    MachineName: str
    Location: Optional[str] = None
    Serial: Optional[str] = None
    TeamID: int

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}


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

    model_config = {"from_attributes": True}
