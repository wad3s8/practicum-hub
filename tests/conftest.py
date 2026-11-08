import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import SessionLocal, engine
from app.main import app
from app.models import Account
from app.security import password_hasher

PASSWORD = "test-password-long-enough"


@pytest.fixture(autouse=True)
def clean_database():
    # Tests must never truncate a development/production database.
    if engine.url.database != "practicum_test":
        pytest.fail("Tests require a dedicated database named practicum_test")
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE project_team_curator, team_member, project_team, project, "
                "team, student, university, account RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin(client):
    with SessionLocal() as db:
        db.add(
            Account(
                full_name="Admin",
                email="admin@example.com",
                password_hash=password_hasher.hash(PASSWORD),
                system_role="admin",
            )
        )
        db.commit()
    response = client.post(
        "/api/v1/auth/login", data={"username": "admin@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def curator(client, admin):
    response = client.post(
        "/api/v1/auth/register",
        headers=admin,
        json={
            "full_name": "Curator",
            "email": "curator@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 201, response.text
    account = response.json()
    token = client.post(
        "/api/v1/auth/login", data={"username": "curator@example.com", "password": PASSWORD}
    )
    return account, {"Authorization": f"Bearer {token.json()['access_token']}"}


@pytest.fixture
def graph(client, curator):
    account, headers = curator

    def create(path, payload):
        response = client.post(f"/api/v1/{path}", headers=headers, json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    university = create("universities", {"name": "UrFU"})
    student = create(
        "students",
        {"university_id": university["id"], "full_name": "Ivan Ivanov", "study_group": "RI-101"},
    )
    team = create("teams", {"name": "Alpha"})
    member = create(
        f"teams/{team['id']}/members", {"student_id": student["id"], "joined_on": "2026-09-01"}
    )
    project = create(
        "projects", {"title": "Bank analytics", "expected_result": "Working prototype"}
    )
    assignment = create(
        "project-teams",
        {
            "project_id": project["id"],
            "team_id": team["id"],
            "period_name": "Autumn 2026",
            "starts_on": "2026-09-01",
            "ends_on": "2026-12-31",
        },
    )
    return {
        "account": account,
        "headers": headers,
        "university": university,
        "student": student,
        "team": team,
        "member": member,
        "project": project,
        "assignment": assignment,
    }
