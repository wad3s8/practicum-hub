from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
LongText = Annotated[str, StringConstraints(max_length=20000)]
Role = Literal["admin", "curator"]
ProjectStatus = Literal["active", "completed", "continuing"]
AssignmentStatus = Literal["active", "completed", "paused"]
PositiveId = Annotated[int, Field(gt=0)]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AccountCreate(Schema):
    full_name: Name
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    system_role: Role = "curator"


class AccountRead(Schema):
    id: int
    full_name: str
    email: str
    system_role: Role
    is_active: bool


class AccountAccessUpdate(Schema):
    system_role: Role | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_null(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class Token(Schema):
    access_token: str
    token_type: str = "bearer"


class UniversityCreate(Schema):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class UniversityRead(UniversityCreate):
    id: int


class StudentCreate(Schema):
    university_id: PositiveId
    full_name: Name
    study_group: ShortText


class StudentUpdate(Schema):
    university_id: PositiveId | None = None
    full_name: Name | None = None
    study_group: ShortText | None = None


class StudentRead(StudentCreate):
    id: int


class TeamCreate(Schema):
    name: Name


class TeamRead(TeamCreate):
    id: int


class MembershipDates(Schema):
    joined_on: date
    left_on: date | None = None

    @model_validator(mode="after")
    def valid_dates(self):
        if self.left_on is not None and self.left_on < self.joined_on:
            raise ValueError("left_on must be on or after joined_on")
        return self


class MemberCreate(MembershipDates):
    student_id: PositiveId
    role: ShortText = "member"


class MemberUpdate(Schema):
    role: ShortText | None = None
    joined_on: date | None = None
    left_on: date | None = None


class MemberRead(MemberCreate):
    id: int
    team_id: int


class ProjectCreate(Schema):
    title: Name
    description: LongText = ""
    expected_result: LongText = ""
    status: ProjectStatus = "active"


class ProjectUpdate(Schema):
    title: Name | None = None
    description: LongText | None = None
    expected_result: LongText | None = None
    status: ProjectStatus | None = None


class ProjectRead(ProjectCreate):
    id: int
    created_by: int


class ProjectTeamCreate(Schema):
    project_id: PositiveId
    team_id: PositiveId
    period_name: ShortText
    starts_on: date
    ends_on: date | None = None
    status: AssignmentStatus = "active"
    result: LongText = ""

    @model_validator(mode="after")
    def valid_dates(self):
        if self.ends_on is not None and self.ends_on < self.starts_on:
            raise ValueError("ends_on must be on or after starts_on")
        return self


class ProjectTeamUpdate(Schema):
    period_name: ShortText | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    status: AssignmentStatus | None = None
    result: LongText | None = None


class ProjectTeamRead(ProjectTeamCreate):
    id: int


class CuratorCreate(MembershipDates):
    account_id: PositiveId


class CuratorUpdate(Schema):
    joined_on: date | None = None
    left_on: date | None = None


class CuratorRead(CuratorCreate):
    id: int
    project_team_id: int
