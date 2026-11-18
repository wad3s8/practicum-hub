from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Account(Base):
    __tablename__ = "account"
    __table_args__ = (CheckConstraint("system_role IN ('admin', 'curator')", name="role"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    system_role: Mapped[str] = mapped_column(String(20), default="curator")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class University(Base):
    __tablename__ = "university"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(300), unique=True)


class Student(Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    university_id: Mapped[int] = mapped_column(
        ForeignKey("university.id", ondelete="RESTRICT"), index=True
    )
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    study_group: Mapped[str] = mapped_column(String(100))


class Team(Base):
    __tablename__ = "team"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))


class TeamMember(Base):
    __tablename__ = "team_member"
    __table_args__ = (
        CheckConstraint("left_on IS NULL OR left_on >= joined_on", name="dates"),
        UniqueConstraint("team_id", "student_id", "joined_on"),
        Index(
            "uq_team_member_active",
            "team_id",
            "student_id",
            unique=True,
            postgresql_where=text("left_on IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id", ondelete="RESTRICT"), index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student.id", ondelete="RESTRICT"), index=True
    )
    role: Mapped[str] = mapped_column(String(100))
    joined_on: Mapped[date] = mapped_column(Date)
    left_on: Mapped[date | None] = mapped_column(Date)


class Project(Base):
    __tablename__ = "project"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'continuing')", name="status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    created_by: Mapped[int] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    expected_result: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    curators: Mapped[list[Account]] = relationship(
        secondary="project_curator", lazy="selectin", order_by=Account.id
    )

    @property
    def curator_ids(self) -> list[int]:
        return [account.id for account in self.curators]


class ProjectCurator(Base):
    __tablename__ = "project_curator"

    project_id: Mapped[int] = mapped_column(ForeignKey("project.id"), primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"), primary_key=True, index=True)


class Meeting(Base):
    __tablename__ = "meeting"
    __table_args__ = (Index("ix_meeting_team_start", "team_id", "starts_at", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ktalk_room_key: Mapped[UUID] = mapped_column(server_default=text("gen_random_uuid()"), unique=True)
    ktalk_url: Mapped[str | None] = mapped_column(String(255))


class ProjectTeam(Base):
    __tablename__ = "project_team"
    __table_args__ = (
        CheckConstraint("ends_on IS NULL OR ends_on >= starts_on", name="dates"),
        CheckConstraint("status IN ('active', 'completed', 'paused')", name="status"),
        UniqueConstraint("project_id", "team_id", "starts_on"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("project.id", ondelete="RESTRICT"), index=True
    )
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id", ondelete="RESTRICT"), index=True)
    period_name: Mapped[str] = mapped_column(String(100))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")
    result: Mapped[str] = mapped_column(Text, default="")


class ProjectTeamCurator(Base):
    __tablename__ = "project_team_curator"
    __table_args__ = (
        CheckConstraint("left_on IS NULL OR left_on >= joined_on", name="dates"),
        UniqueConstraint("project_team_id", "account_id", "joined_on"),
        Index(
            "uq_project_team_curator_active",
            "project_team_id",
            "account_id",
            unique=True,
            postgresql_where=text("left_on IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    project_team_id: Mapped[int] = mapped_column(
        ForeignKey("project_team.id", ondelete="RESTRICT"), index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("account.id", ondelete="RESTRICT"), index=True
    )
    joined_on: Mapped[date] = mapped_column(Date)
    left_on: Mapped[date | None] = mapped_column(Date)
