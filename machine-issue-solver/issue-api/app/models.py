"""
SQLAlchemy ORM models mapping to existing SQLite database schema

Tables:
  - Lines (LineID, LineName)
  - Teams (TeamID, TeamName, LineID)
  - Machines (MachineID, MachineName, Location, Serial, TeamID)
  - Issues (IssueID, MachineID, Date, "Start Time", "Total Time", Week, Year,
            "Hiện tượng", "Nguyên nhân", "Khắc phục", PIC, "User Input")
"""

from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class Line(Base):
    __tablename__ = "Lines"

    LineID = Column(Integer, primary_key=True)
    LineName = Column(Text)

    teams = relationship("Team", back_populates="line", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "Teams"

    TeamID = Column(Integer, primary_key=True)
    TeamName = Column(Text)
    LineID = Column(Integer, ForeignKey("Lines.LineID"), nullable=False)

    line = relationship("Line", back_populates="teams")
    machines = relationship("Machine", back_populates="team", cascade="all, delete-orphan")


class Machine(Base):
    __tablename__ = "Machines"

    MachineID = Column(Integer, primary_key=True)
    MachineName = Column(Text, nullable=False)
    Location = Column(Text)
    Serial = Column(Text)
    TeamID = Column(Integer, ForeignKey("Teams.TeamID"), nullable=False)

    team = relationship("Team", back_populates="machines")
    issues = relationship("Issue", back_populates="machine", cascade="all, delete-orphan")


class Issue(Base):
    __tablename__ = "Issues"

    IssueID = Column(Integer, primary_key=True)
    MachineID = Column(Integer, ForeignKey("Machines.MachineID"), nullable=False)
    Date = Column(Text)
    start_time = Column("Start Time", Text)
    total_time = Column("Total Time", Text)
    Week = Column(Integer)
    Year = Column(Integer)
    hien_tuong = Column("Hiện tượng", Text)    # Symptom
    nguyen_nhan = Column("Nguyên nhân", Text)  # Cause
    khac_phuc = Column("Khắc phục", Text)      # Solution
    PIC = Column(Text)
    user_input = Column("User Input", Text)

    machine = relationship("Machine", back_populates="issues")
