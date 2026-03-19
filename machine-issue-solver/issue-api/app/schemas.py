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
    LineID: int

    model_config = {"from_attributes": True}


# ---- Machine ----

class MachineResponse(BaseModel):
    MachineID: int
    MachineName: str
    TeamID: int

    model_config = {"from_attributes": True}


# ---- Issue ----

class IssueCreate(BaseModel):
    MachineID: int
    hien_tuong: Optional[str] = None   # Symptom
    nguyen_nhan: Optional[str] = None  # Cause
    khac_phuc: Optional[str] = None    # Solution


class IssueUpdate(BaseModel):
    MachineID: Optional[int] = None
    hien_tuong: Optional[str] = None
    nguyen_nhan: Optional[str] = None
    khac_phuc: Optional[str] = None


class IssueResponse(BaseModel):
    IssueID: int
    MachineID: int
    hien_tuong: Optional[str] = None
    nguyen_nhan: Optional[str] = None
    khac_phuc: Optional[str] = None

    model_config = {"from_attributes": True}


class IssueSearchResult(BaseModel):
    """Response for the search endpoint — includes machine and line context"""
    IssueID: int
    MachineID: int
    hien_tuong: Optional[str] = None
    nguyen_nhan: Optional[str] = None
    khac_phuc: Optional[str] = None
    MachineName: str
    LineName: str

    model_config = {"from_attributes": True}
