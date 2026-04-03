"""
SQLAlchemy ORM models for PostgreSQL database

Schema:
  - teams (id, name, created_at)
  - lines (id, team_id, name, created_at)  
  - machines (id, line_id, name, location, serial, created_at)
  - issues (id, machine_id, date, start_time, stop_time, total_time, week, year,
            hien_tuong, nguyen_nhan, khac_phuc, pic, user_input, created_at)
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from database import Base


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    lines = relationship("Line", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Team(id={self.id}, name='{self.name}')>"


class Line(Base):
    __tablename__ = "lines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    line_number = Column(Integer, nullable=False)  # Changed from name to line_number (integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    team = relationship("Team", back_populates="lines")
    machines = relationship("Machine", back_populates="line", cascade="all, delete-orphan")

    # Unique constraint handled by Index below
    __table_args__ = (
        Index('idx_lines_team_number', 'team_id', 'line_number', unique=True),
    )

    def __repr__(self):
        return f"<Line(id={self.id}, name='{self.name}', team_id={self.team_id})>"


class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    line_id = Column(Integer, ForeignKey("lines.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    serial = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    line = relationship("Line", back_populates="machines")
    issues = relationship("Issue", back_populates="machine", cascade="all, delete-orphan")

    # Indexes for fast search
    __table_args__ = (
        Index('idx_machines_search', 'line_id', 'name', 'location', 'serial'),
        Index('idx_machines_unique', 'line_id', 'name', 'location', 'serial', unique=True, 
              postgresql_where="(location IS NOT NULL OR serial IS NOT NULL)"),
    )

    def __repr__(self):
        return f"<Machine(id={self.id}, name='{self.name}', line_id={self.line_id})>"


class Issue(Base):
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(Integer, ForeignKey("machines.id", ondelete="CASCADE"), nullable=False)
    
    # Issue details
    date = Column(DateTime, nullable=True)
    start_time = Column(String(50), nullable=True)
    stop_time = Column(String(50), nullable=True)
    total_time = Column(String(50), nullable=True)
    week = Column(Integer, nullable=True)
    year = Column(Integer, nullable=True)
    hien_tuong = Column(Text, nullable=True)      # Hiện tượng (Symptom)
    nguyen_nhan = Column(Text, nullable=True)     # Nguyên nhân (Cause)
    khac_phuc = Column(Text, nullable=True)       # Khắc phục (Solution)
    pic = Column(String(255), nullable=True)      # PIC
    user_input = Column(Text, nullable=True)      # User Input
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    machine = relationship("Machine", back_populates="issues")

    # Indexes
    __table_args__ = (
        Index('idx_issues_machine', 'machine_id'),
        Index('idx_issues_machine_hien_tuong', 'machine_id', 'hien_tuong'),  # For duplicate check
    )

    def __repr__(self):
        return f"<Issue(id={self.id}, machine_id={self.machine_id})>"
