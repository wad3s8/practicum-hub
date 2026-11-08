from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from app import models as m
from app import schemas as s
from app.security import CurrentAccount, Db, current_account
from app.services import delete_unreferenced, get_or_404, list_records, merged_values, save, update

router = APIRouter(dependencies=[Depends(current_account)])
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


@router.post(
    "/universities", response_model=s.UniversityRead, status_code=201, tags=["Universities"]
)
def create_university(payload: s.UniversityCreate, db: Db):
    return save(db, m.University(**payload.model_dump()))


@router.get("/universities", response_model=list[s.UniversityRead], tags=["Universities"])
def universities(db: Db, offset: Offset = 0, limit: Limit = 50):
    return list_records(db, m.University, offset, limit)


@router.patch(
    "/universities/{university_id}", response_model=s.UniversityRead, tags=["Universities"]
)
def edit_university(university_id: int, payload: s.UniversityCreate, db: Db):
    return update(db, get_or_404(db, m.University, university_id), payload, s.UniversityCreate)


@router.delete("/universities/{university_id}", status_code=204, tags=["Universities"])
def delete_university(university_id: int, db: Db):
    delete_unreferenced(db, get_or_404(db, m.University, university_id))
    return Response(status_code=204)


def check_student_duplicate(db, payload: s.StudentCreate, allow_duplicate: bool, exclude_id=None):
    if allow_duplicate:
        return
    query = select(m.Student.id).where(
        m.Student.university_id == payload.university_id,
        func.lower(m.Student.full_name) == payload.full_name.lower(),
        func.lower(m.Student.study_group) == payload.study_group.lower(),
    )
    if exclude_id is not None:
        query = query.where(m.Student.id != exclude_id)
    candidates = list(db.scalars(query.limit(20)))
    if candidates:
        raise HTTPException(
            409,
            {
                "message": "Possible duplicate student. Review matches; use allow_duplicate=true to confirm.",
                "student_ids": candidates,
            },
        )


@router.post("/students", response_model=s.StudentRead, status_code=201, tags=["Students"])
def create_student(payload: s.StudentCreate, db: Db, allow_duplicate: bool = False):
    get_or_404(db, m.University, payload.university_id)
    check_student_duplicate(db, payload, allow_duplicate)
    return save(db, m.Student(**payload.model_dump()))


@router.get("/students", response_model=list[s.StudentRead], tags=["Students"])
def students(
    db: Db,
    q: Annotated[str | None, Query(max_length=200)] = None,
    university_id: int | None = None,
    team_id: int | None = None,
    offset: Offset = 0,
    limit: Limit = 50,
):
    filters = []
    if q:
        filters.append(m.Student.full_name.icontains(q, autoescape=True))
    if university_id is not None:
        filters.append(m.Student.university_id == university_id)
    if team_id is not None:
        filters.append(
            m.Student.id.in_(select(m.TeamMember.student_id).where(m.TeamMember.team_id == team_id))
        )
    return list_records(db, m.Student, offset, limit, *filters)


@router.get("/students/{student_id}", response_model=s.StudentRead, tags=["Students"])
def student(student_id: int, db: Db):
    return get_or_404(db, m.Student, student_id)


@router.patch("/students/{student_id}", response_model=s.StudentRead, tags=["Students"])
def edit_student(student_id: int, payload: s.StudentUpdate, db: Db, allow_duplicate: bool = False):
    item = get_or_404(db, m.Student, student_id)
    values = merged_values(item, payload, s.StudentCreate)
    get_or_404(db, m.University, values.university_id)
    check_student_duplicate(db, values, allow_duplicate, exclude_id=student_id)
    return update(db, item, payload, s.StudentCreate)


@router.delete("/students/{student_id}", status_code=204, tags=["Students"])
def delete_student(student_id: int, db: Db):
    delete_unreferenced(db, get_or_404(db, m.Student, student_id))
    return Response(status_code=204)


@router.get(
    "/students/{student_id}/memberships", response_model=list[s.MemberRead], tags=["Students"]
)
def student_memberships(student_id: int, db: Db, offset: Offset = 0, limit: Limit = 50):
    get_or_404(db, m.Student, student_id)
    return list_records(db, m.TeamMember, offset, limit, m.TeamMember.student_id == student_id)


@router.post("/teams", response_model=s.TeamRead, status_code=201, tags=["Teams"])
def create_team(payload: s.TeamCreate, db: Db):
    return save(db, m.Team(**payload.model_dump()))


@router.get("/teams", response_model=list[s.TeamRead], tags=["Teams"])
def teams(
    db: Db,
    q: Annotated[str | None, Query(max_length=200)] = None,
    offset: Offset = 0,
    limit: Limit = 50,
):
    filters = [m.Team.name.icontains(q, autoescape=True)] if q else []
    return list_records(db, m.Team, offset, limit, *filters)


@router.get("/teams/{team_id}", response_model=s.TeamRead, tags=["Teams"])
def team(team_id: int, db: Db):
    return get_or_404(db, m.Team, team_id)


@router.patch("/teams/{team_id}", response_model=s.TeamRead, tags=["Teams"])
def edit_team(team_id: int, payload: s.TeamCreate, db: Db):
    return update(db, get_or_404(db, m.Team, team_id), payload, s.TeamCreate)


@router.delete("/teams/{team_id}", status_code=204, tags=["Teams"])
def delete_team(team_id: int, db: Db):
    delete_unreferenced(db, get_or_404(db, m.Team, team_id))
    return Response(status_code=204)


@router.post(
    "/teams/{team_id}/members", response_model=s.MemberRead, status_code=201, tags=["Team members"]
)
def add_member(team_id: int, payload: s.MemberCreate, db: Db):
    get_or_404(db, m.Team, team_id)
    get_or_404(db, m.Student, payload.student_id)
    return save(db, m.TeamMember(team_id=team_id, **payload.model_dump()))


@router.get("/teams/{team_id}/members", response_model=list[s.MemberRead], tags=["Team members"])
def members(team_id: int, db: Db, active_only: bool = False, offset: Offset = 0, limit: Limit = 50):
    get_or_404(db, m.Team, team_id)
    filters = [m.TeamMember.team_id == team_id]
    if active_only:
        filters.append(m.TeamMember.left_on.is_(None))
    return list_records(db, m.TeamMember, offset, limit, *filters)


@router.patch(
    "/teams/{team_id}/members/{member_id}", response_model=s.MemberRead, tags=["Team members"]
)
def edit_member(team_id: int, member_id: int, payload: s.MemberUpdate, db: Db):
    item = get_or_404(db, m.TeamMember, member_id)
    if item.team_id != team_id:
        raise HTTPException(404, "Membership not found in this team")
    return update(db, item, payload, s.MemberCreate)


@router.post("/projects", response_model=s.ProjectRead, status_code=201, tags=["Projects"])
def create_project(payload: s.ProjectCreate, db: Db, account: CurrentAccount):
    return save(db, m.Project(created_by=account.id, **payload.model_dump()))


@router.get("/projects", response_model=list[s.ProjectRead], tags=["Projects"])
def projects(
    db: Db,
    status: s.ProjectStatus | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    offset: Offset = 0,
    limit: Limit = 50,
):
    filters = []
    if status is not None:
        filters.append(m.Project.status == status)
    if q:
        filters.append(m.Project.title.icontains(q, autoescape=True))
    return list_records(db, m.Project, offset, limit, *filters)


@router.get("/projects/{project_id}", response_model=s.ProjectRead, tags=["Projects"])
def project(project_id: int, db: Db):
    return get_or_404(db, m.Project, project_id)


@router.patch("/projects/{project_id}", response_model=s.ProjectRead, tags=["Projects"])
def edit_project(project_id: int, payload: s.ProjectUpdate, db: Db):
    return update(db, get_or_404(db, m.Project, project_id), payload, s.ProjectCreate)


@router.delete("/projects/{project_id}", status_code=204, tags=["Projects"])
def delete_project(project_id: int, db: Db):
    delete_unreferenced(db, get_or_404(db, m.Project, project_id))
    return Response(status_code=204)


@router.post(
    "/project-teams", response_model=s.ProjectTeamRead, status_code=201, tags=["Project teams"]
)
def create_assignment(payload: s.ProjectTeamCreate, db: Db):
    get_or_404(db, m.Project, payload.project_id)
    get_or_404(db, m.Team, payload.team_id)
    return save(db, m.ProjectTeam(**payload.model_dump()))


@router.get("/project-teams", response_model=list[s.ProjectTeamRead], tags=["Project teams"])
def assignments(
    db: Db,
    project_id: int | None = None,
    team_id: int | None = None,
    curator_id: int | None = None,
    period_name: str | None = None,
    status: s.AssignmentStatus | None = None,
    offset: Offset = 0,
    limit: Limit = 50,
):
    filters = []
    for field, value in (
        ("project_id", project_id),
        ("team_id", team_id),
        ("period_name", period_name),
        ("status", status),
    ):
        if value is not None:
            filters.append(getattr(m.ProjectTeam, field) == value)
    if curator_id is not None:
        filters.append(
            m.ProjectTeam.id.in_(
                select(m.ProjectTeamCurator.project_team_id).where(
                    m.ProjectTeamCurator.account_id == curator_id
                )
            )
        )
    return list_records(db, m.ProjectTeam, offset, limit, *filters)


@router.get(
    "/project-teams/{assignment_id}", response_model=s.ProjectTeamRead, tags=["Project teams"]
)
def assignment(assignment_id: int, db: Db):
    return get_or_404(db, m.ProjectTeam, assignment_id)


@router.patch(
    "/project-teams/{assignment_id}", response_model=s.ProjectTeamRead, tags=["Project teams"]
)
def edit_assignment(assignment_id: int, payload: s.ProjectTeamUpdate, db: Db):
    return update(db, get_or_404(db, m.ProjectTeam, assignment_id), payload, s.ProjectTeamCreate)


@router.delete("/project-teams/{assignment_id}", status_code=204, tags=["Project teams"])
def delete_assignment(assignment_id: int, db: Db):
    delete_unreferenced(db, get_or_404(db, m.ProjectTeam, assignment_id))
    return Response(status_code=204)


@router.post(
    "/project-teams/{assignment_id}/curators",
    response_model=s.CuratorRead,
    status_code=201,
    tags=["Project team curators"],
)
def add_curator(assignment_id: int, payload: s.CuratorCreate, db: Db):
    get_or_404(db, m.ProjectTeam, assignment_id)
    account = get_or_404(db, m.Account, payload.account_id)
    if account.system_role != "curator" or not account.is_active:
        raise HTTPException(422, "An active curator account is required")
    return save(db, m.ProjectTeamCurator(project_team_id=assignment_id, **payload.model_dump()))


@router.get(
    "/project-teams/{assignment_id}/curators",
    response_model=list[s.CuratorRead],
    tags=["Project team curators"],
)
def curators(
    assignment_id: int, db: Db, active_only: bool = False, offset: Offset = 0, limit: Limit = 50
):
    get_or_404(db, m.ProjectTeam, assignment_id)
    filters = [m.ProjectTeamCurator.project_team_id == assignment_id]
    if active_only:
        filters.append(m.ProjectTeamCurator.left_on.is_(None))
    return list_records(db, m.ProjectTeamCurator, offset, limit, *filters)


@router.patch(
    "/project-teams/{assignment_id}/curators/{curator_id}",
    response_model=s.CuratorRead,
    tags=["Project team curators"],
)
def edit_curator(assignment_id: int, curator_id: int, payload: s.CuratorUpdate, db: Db):
    item = get_or_404(db, m.ProjectTeamCurator, curator_id)
    if item.project_team_id != assignment_id:
        raise HTTPException(404, "Curator assignment not found in this project team")
    return update(db, item, payload, s.CuratorCreate)
