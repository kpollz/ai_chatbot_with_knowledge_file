"""
SQLAlchemy ORM models mapping to existing SQLite database schema

Tables:
  - Lines (LineID, LineName)
  - Teams (TeamID, LineID)
  - Machines (MachineID, MachineName, TeamID)
  - Issues (IssueID, MachineID, "Hien tuong", "Nguyen nhan", "Khac phuc")
"""

from sqlalchemy import Column, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship

from database import Base


class Line(Base):
    __tablename__ = "Lines"

    LineID = Column(Integer, primary_key=True, autoincrement=True)
    LineName = Column(Text, nullable=False)

    teams = relationship("Team", back_populates="line", cascade="all, delete-orphan")


class Team(Base):
    __tablename__ = "Teams"

    TeamID = Column(Integer, primary_key=True, autoincrement=True)
    LineID = Column(Integer, ForeignKey("Lines.LineID"), nullable=False)

    line = relationship("Line", back_populates="teams")
    machines = relationship("Machine", back_populates="team", cascade="all, delete-orphan")


class Machine(Base):
    __tablename__ = "Machines"

    MachineID = Column(Integer, primary_key=True, autoincrement=True)
    MachineName = Column(Text, nullable=False)
    TeamID = Column(Integer, ForeignKey("Teams.TeamID"), nullable=False)

    team = relationship("Team", back_populates="machines")
    issues = relationship("Issue", back_populates="machine", cascade="all, delete-orphan")


class Issue(Base):
    __tablename__ = "Issues"

    IssueID = Column(Integer, primary_key=True, autoincrement=True)
    MachineID = Column(Integer, ForeignKey("Machines.MachineID"), nullable=False)
    hien_tuong = Column("Hien tuong", Text)   # Symptom
    nguyen_nhan = Column("Nguyen nhan", Text)  # Cause
    khac_phuc = Column("Khac phuc", Text)      # Solution

    machine = relationship("Machine", back_populates="issues")
