from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Account
from tests.conftest import PASSWORD

PREFIX = "/api/v1"


@pytest.mark.parametrize(
    "path", ["projects", "students", "teams", "project-teams", "universities", "accounts"]
)
def test_resources_require_authentication(client, path):
    assert client.get(f"{PREFIX}/{path}").status_code == 401
    if path != "accounts":
        assert client.post(f"{PREFIX}/{path}", json={}).status_code == 401


def test_registration_is_admin_only_and_password_is_hashed(client, admin, curator):
    payload = {"full_name": "New Employee", "email": "new@example.com", "password": PASSWORD}
    assert client.post(f"{PREFIX}/auth/register", json=payload).status_code == 401
    assert (
        client.post(f"{PREFIX}/auth/register", headers=curator[1], json=payload).status_code == 403
    )
    response = client.post(f"{PREFIX}/auth/register", headers=admin, json=payload)
    assert response.status_code == 201
    assert "password" not in response.json() and "password_hash" not in response.json()
    with SessionLocal() as db:
        account = db.scalar(select(Account).where(Account.email == "new@example.com"))
        assert account.password_hash.startswith("$argon2")
        assert account.password_hash != PASSWORD
    payload["email"] = "NEW@example.com"
    assert client.post(f"{PREFIX}/auth/register", headers=admin, json=payload).status_code == 409
    payload["email"] = "student@example.com"
    payload["system_role"] = "student"
    assert client.post(f"{PREFIX}/auth/register", headers=admin, json=payload).status_code == 422


def test_login_me_invalid_and_expired_tokens(client, admin):
    assert client.get(f"{PREFIX}/auth/me", headers=admin).json()["email"] == "admin@example.com"
    for username in ["admin@example.com", "missing@example.com"]:
        assert (
            client.post(
                f"{PREFIX}/auth/login", data={"username": username, "password": "wrong"}
            ).status_code
            == 401
        )
    token = jwt.encode(
        {
            "sub": "1",
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(hours=1),
        },
        get_settings().jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    for value in [token, "invalid.token", admin["Authorization"].split()[1] + "tampered"]:
        assert (
            client.get(
                f"{PREFIX}/auth/me", headers={"Authorization": f"Bearer {value}"}
            ).status_code
            == 401
        )


def test_deactivation_immediately_blocks_existing_token(client, admin, curator):
    account, headers = curator
    assert (
        client.patch(
            f"{PREFIX}/accounts/{account['id']}/access",
            headers=headers,
            json={"system_role": "admin"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{PREFIX}/accounts/{account['id']}/access", headers=admin, json={"is_active": False}
        ).status_code
        == 200
    )
    assert client.get(f"{PREFIX}/projects", headers=headers).status_code == 401
    assert (
        client.post(
            f"{PREFIX}/auth/login", data={"username": account["email"], "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.patch(
            f"{PREFIX}/accounts/1/access", headers=admin, json={"is_active": False}
        ).status_code
        == 409
    )


def test_complete_workflow_and_project_period_history(client, graph):
    g, headers = graph, graph["headers"]
    project, team, student = g["project"], g["team"], g["student"]
    assert project["created_by"] == g["account"]["id"]
    assert "owner_id" not in project
    assert "account_id" not in student
    assignment = g["assignment"]
    assert (
        client.patch(
            f"{PREFIX}/project-teams/{assignment['id']}",
            headers=headers,
            json={"status": "completed", "result": "Prototype delivered"},
        ).status_code
        == 200
    )
    next_period = client.post(
        f"{PREFIX}/project-teams",
        headers=headers,
        json={
            "project_id": project["id"],
            "team_id": team["id"],
            "period_name": "Spring 2027",
            "starts_on": "2027-02-01",
        },
    )
    assert next_period.status_code == 201
    assert (
        len(
            client.get(
                f"{PREFIX}/project-teams", headers=headers, params={"project_id": project["id"]}
            ).json()
        )
        == 2
    )
    assert len(client.get(f"{PREFIX}/teams/{team['id']}/members", headers=headers).json()) == 1
    assert (
        client.get(f"{PREFIX}/project-teams/{assignment['id']}", headers=headers).json()["result"]
        == "Prototype delivered"
    )
    found = client.get(
        f"{PREFIX}/students", headers=headers, params={"q": "ivan", "team_id": team["id"]}
    ).json()
    assert [item["id"] for item in found] == [student["id"]]
    assert (
        len(client.get(f"{PREFIX}/students/{student['id']}/memberships", headers=headers).json())
        == 1
    )


def test_member_history_and_multiple_teams(client, graph):
    g, h = graph, graph["headers"]
    path = f"{PREFIX}/teams/{g['team']['id']}/members"
    payload = {"student_id": g["student"]["id"], "joined_on": "2027-01-01"}
    assert client.post(path, headers=h, json=payload).status_code == 409
    assert (
        client.patch(
            f"{path}/{g['member']['id']}", headers=h, json={"left_on": "2026-12-31"}
        ).status_code
        == 200
    )
    assert client.post(path, headers=h, json=payload).status_code == 201
    assert len(client.get(path, headers=h).json()) == 2
    assert len(client.get(path, headers=h, params={"active_only": True}).json()) == 1
    second = client.post(f"{PREFIX}/teams", headers=h, json={"name": "Beta"}).json()
    assert (
        client.post(f"{PREFIX}/teams/{second['id']}/members", headers=h, json=payload).status_code
        == 201
    )
    assert (
        len(client.get(f"{PREFIX}/students/{g['student']['id']}/memberships", headers=h).json())
        == 3
    )
    assert (
        client.patch(
            f"{PREFIX}/teams/{second['id']}/members/{g['member']['id']}",
            headers=h,
            json={"role": "lead"},
        ).status_code
        == 404
    )


def test_curators_belong_to_project_team(client, graph):
    g, h = graph, graph["headers"]
    path = f"{PREFIX}/project-teams/{g['assignment']['id']}/curators"
    payload = {"account_id": g["account"]["id"], "joined_on": "2026-09-01"}
    response = client.post(path, headers=h, json=payload)
    assert response.status_code == 201
    assert response.json()["project_team_id"] == g["assignment"]["id"]
    assert "team_id" not in response.json()
    assert client.post(path, headers=h, json=payload).status_code == 409
    found = client.get(
        f"{PREFIX}/project-teams", headers=h, params={"curator_id": g["account"]["id"]}
    ).json()
    assert [item["id"] for item in found] == [g["assignment"]["id"]]
    assert (
        client.patch(
            f"{path}/{response.json()['id']}", headers=h, json={"left_on": "2026-12-31"}
        ).status_code
        == 200
    )
    assert client.get(path, headers=h, params={"active_only": True}).json() == []
    assert len(client.get(path, headers=h).json()) == 1
    assert (
        client.post(path, headers=h, json={"account_id": 1, "joined_on": "2026-09-01"}).status_code
        == 422
    )


def test_duplicate_student_warning_can_be_confirmed(client, graph):
    g, h = graph, graph["headers"]
    payload = {key: value for key, value in g["student"].items() if key != "id"}
    response = client.post(f"{PREFIX}/students", headers=h, json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["student_ids"] == [g["student"]["id"]]
    response = client.post(f"{PREFIX}/students?allow_duplicate=true", headers=h, json=payload)
    assert response.status_code == 201
    assert response.json()["id"] != g["student"]["id"]
    assert (
        client.patch(
            f"{PREFIX}/students/{g['student']['id']}", headers=h, json={"study_group": "RI-201"}
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    "resource,key",
    [
        ("projects", "project"),
        ("teams", "team"),
        ("students", "student"),
        ("universities", "university"),
    ],
)
def test_deletion_protects_history(client, graph, resource, key):
    response = client.delete(f"{PREFIX}/{resource}/{graph[key]['id']}", headers=graph["headers"])
    assert response.status_code == 409


def test_validation_and_missing_references(client, graph):
    g, h = graph, graph["headers"]
    assert (
        client.patch(
            f"{PREFIX}/projects/{g['project']['id']}", headers=h, json={"title": None}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{PREFIX}/projects/{g['project']['id']}", headers=h, json={"title": "   "}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{PREFIX}/projects", headers=h, json={"title": "Test", "created_by": 1}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{PREFIX}/students",
            headers=h,
            json={"full_name": "Test", "study_group": "G", "university_id": 9999},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"{PREFIX}/project-teams/{g['assignment']['id']}",
            headers=h,
            json={"ends_on": "2025-01-01"},
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{PREFIX}/teams/{g['team']['id']}/members/{g['member']['id']}",
            headers=h,
            json={"left_on": "2025-01-01"},
        ).status_code
        == 422
    )
    assert client.get(f"{PREFIX}/projects/999999", headers=h).status_code == 404
    assert client.get(f"{PREFIX}/projects", headers=h, params={"limit": 101}).status_code == 422
    assert (
        client.get(f"{PREFIX}/projects", headers=h, params={"status": "unknown"}).status_code == 422
    )


def test_unreferenced_crud_and_health(client, curator):
    h = curator[1]
    for resource, payload, edit in [
        ("projects", {"title": "First"}, {"title": "Renamed", "status": "continuing"}),
        ("teams", {"name": "First"}, {"name": "Renamed"}),
    ]:
        created = client.post(f"{PREFIX}/{resource}", headers=h, json=payload)
        assert created.status_code == 201
        path = f"{PREFIX}/{resource}/{created.json()['id']}"
        assert client.get(path, headers=h).status_code == 200
        response = client.patch(path, headers=h, json=edit)
        assert response.status_code == 200
        assert all(response.json()[key] == value for key, value in edit.items())
        assert client.delete(path, headers=h).status_code == 204
        assert client.get(path, headers=h).status_code == 404
    assert client.get("/health").json() == {"status": "ok"}


def test_bootstrap_creates_first_admin_only(client, monkeypatch):
    from app import bootstrap

    def run_bootstrap():
        answers = iter(["First Admin", "first@example.com"])
        monkeypatch.setattr("builtins.input", lambda _: next(answers))
        monkeypatch.setattr(bootstrap, "getpass", lambda _: PASSWORD)
        bootstrap.main()

    run_bootstrap()
    response = client.post(
        f"{PREFIX}/auth/login", data={"username": "first@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    with pytest.raises(SystemExit, match="administrator already exists"):
        run_bootstrap()


def test_student_has_no_account_and_password_validation(client, admin, graph):
    student = {key: value for key, value in graph["student"].items() if key != "id"}
    student["account_id"] = 1
    assert client.post(f"{PREFIX}/students", headers=admin, json=student).status_code == 422
    assert (
        client.post(
            f"{PREFIX}/auth/register",
            headers=admin,
            json={
                "full_name": "Test",
                "email": "short@example.com",
                "password": "short",
            },
        ).status_code
        == 422
    )
