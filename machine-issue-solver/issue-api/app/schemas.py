"""
Pydantic schemas for request/response validation
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import re

# Shared config
_response_config = {"from_attributes": True}


# ---- Team ----

class TeamCreate(BaseModel):
    name: str = Field(..., alias="TeamName")

    class Config:
        populate_by_name = True


class TeamResponse(BaseModel):
    id: int = Field(..., alias="TeamID")
    name: Optional[str] = Field(None, alias="TeamName")

    model_config = {**_response_config, "populate_by_name": True}


# ---- Line ----

class LineCreate(BaseModel):
    line_number: int = Field(..., alias="LineName")
    
    @field_validator('line_number', mode='before')
    @classmethod
    def parse_line_number(cls, v):
        """Parse line number string (e.g., '2', '02') to integer"""
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            return int(v.strip())
        raise ValueError(f"Line number must be string or int, got {type(v)}")

    class Config:
        populate_by_name = True


class LineResponse(BaseModel):
    id: int = Field(..., alias="LineID")
    line_number: int = Field(..., alias="LineName")

    model_config = {**_response_config, "populate_by_name": True}


# ---- Machine ----

class MachineCreate(BaseModel):
    name: str = Field(..., alias="MachineName")
    location: Optional[str] = Field(None, alias="Location")
    serial: Optional[str] = Field(None, alias="Serial")
    line_id: int = Field(..., alias="LineID")

    class Config:
        populate_by_name = True


class MachineUpdate(BaseModel):
    name: Optional[str] = Field(None, alias="MachineName")
    location: Optional[str] = Field(None, alias="Location")
    serial: Optional[str] = Field(None, alias="Serial")
    line_id: Optional[int] = Field(None, alias="LineID")

    class Config:
        populate_by_name = True


class MachineResponse(BaseModel):
    id: int = Field(..., alias="MachineID")
    name: Optional[str] = Field(None, alias="MachineName")
    location: Optional[str] = Field(None, alias="Location")
    serial: Optional[str] = Field(None, alias="Serial")
    line_id: int = Field(..., alias="LineID")

    model_config = {**_response_config, "populate_by_name": True}


# ---- Issue ----

class IssueCreate(BaseModel):
    machine_id: int = Field(..., alias="MachineID")
    date: Optional[str] = Field(None, alias="Date")
    start_time: Optional[str] = Field(None, alias="start_time")
    stop_time: Optional[str] = Field(None, alias="stop_time")
    total_time: Optional[str] = Field(None, alias="total_time")
    week: Optional[int] = Field(None, alias="Week")
    year: Optional[int] = Field(None, alias="Year")
    hien_tuong: Optional[str] = Field(None, alias="hien_tuong")
    nguyen_nhan: Optional[str] = Field(None, alias="nguyen_nhan")
    khac_phuc: Optional[str] = Field(None, alias="khac_phuc")
    pic: Optional[str] = Field(None, alias="PIC")
    user_input: Optional[str] = Field(None, alias="user_input")

    class Config:
        populate_by_name = True


class IssueUpdate(BaseModel):
    machine_id: Optional[int] = Field(None, alias="MachineID")
    date: Optional[str] = Field(None, alias="Date")
    start_time: Optional[str] = Field(None, alias="start_time")
    stop_time: Optional[str] = Field(None, alias="stop_time")
    total_time: Optional[str] = Field(None, alias="total_time")
    week: Optional[int] = Field(None, alias="Week")
    year: Optional[int] = Field(None, alias="Year")
    hien_tuong: Optional[str] = Field(None, alias="hien_tuong")
    nguyen_nhan: Optional[str] = Field(None, alias="nguyen_nhan")
    khac_phuc: Optional[str] = Field(None, alias="khac_phuc")
    pic: Optional[str] = Field(None, alias="PIC")
    user_input: Optional[str] = Field(None, alias="user_input")

    class Config:
        populate_by_name = True


class IssueResponse(BaseModel):
    id: int = Field(..., alias="IssueID")
    machine_id: int = Field(..., alias="MachineID")
    date: Optional[str] = Field(None, alias="Date")
    start_time: Optional[str] = Field(None, alias="start_time")
    stop_time: Optional[str] = Field(None, alias="stop_time")
    total_time: Optional[str] = Field(None, alias="total_time")
    week: Optional[int] = Field(None, alias="Week")
    year: Optional[int] = Field(None, alias="Year")
    hien_tuong: Optional[str] = Field(None, alias="hien_tuong")
    nguyen_nhan: Optional[str] = Field(None, alias="nguyen_nhan")
    khac_phuc: Optional[str] = Field(None, alias="khac_phuc")
    pic: Optional[str] = Field(None, alias="PIC")
    user_input: Optional[str] = Field(None, alias="user_input")

    model_config = {**_response_config, "populate_by_name": True}


# ---- Import (convenience for Excel row) ----

class IssueImportRequest(BaseModel):
    """Import a full Excel row — auto-creates Team/Line/Machine if not found."""
    team_name: str = Field(..., alias="TeamName")
    line_name: str = Field(..., alias="LineName")
    machine_name: str = Field(..., alias="MachineName")
    location: Optional[str] = Field(None, alias="Location")
    serial: Optional[str] = Field(None, alias="Serial")
    date: Optional[str] = Field(None, alias="Date")
    start_time: Optional[str] = Field(None, alias="start_time")
    stop_time: Optional[str] = Field(None, alias="stop_time")
    total_time: Optional[str] = Field(None, alias="total_time")
    week: Optional[int] = Field(None, alias="Week")
    year: Optional[int] = Field(None, alias="Year")
    hien_tuong: Optional[str] = Field(None, alias="hien_tuong")
    nguyen_nhan: Optional[str] = Field(None, alias="nguyen_nhan")
    khac_phuc: Optional[str] = Field(None, alias="khac_phuc")
    pic: Optional[str] = Field(None, alias="PIC")
    user_input: Optional[str] = Field(None, alias="user_input")

    class Config:
        populate_by_name = True


class IssueImportResponse(BaseModel):
    """Response for import — includes what was created vs reused."""
    issue_id: int = Field(..., alias="IssueID")
    machine_id: int = Field(..., alias="MachineID")
    line_id: int = Field(..., alias="LineID")
    team_id: int = Field(..., alias="TeamID")
    created_team: bool = Field(False, alias="created_team")
    created_line: bool = Field(False, alias="created_line")
    created_machine: bool = Field(False, alias="created_machine")
    is_duplicate: bool = Field(False, alias="is_duplicate")

    model_config = {**_response_config, "populate_by_name": True}


# ---- Search Result ----

class IssueSearchResult(BaseModel):
    """Response for the search endpoint — includes machine and line context"""
    issue_id: int = Field(..., alias="IssueID")
    machine_id: int = Field(..., alias="MachineID")
    date: Optional[str] = Field(None, alias="Date")
    start_time: Optional[str] = Field(None, alias="start_time")
    stop_time: Optional[str] = Field(None, alias="stop_time")
    total_time: Optional[str] = Field(None, alias="total_time")
    hien_tuong: Optional[str] = Field(None, alias="hien_tuong")
    nguyen_nhan: Optional[str] = Field(None, alias="nguyen_nhan")
    khac_phuc: Optional[str] = Field(None, alias="khac_phuc")
    pic: Optional[str] = Field(None, alias="PIC")
    machine_name: Optional[str] = Field(None, alias="MachineName")
    line_number: int = Field(..., alias="LineName")  # Changed to int
    location: Optional[str] = Field(None, alias="Location")
    serial: Optional[str] = Field(None, alias="Serial")

    model_config = {**_response_config, "populate_by_name": True}
