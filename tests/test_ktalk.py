import httpx
from pydantic import SecretStr

from app.config import get_settings


def test_attach_room_and_retry(client, graph, monkeypatch):
    headers = graph["headers"]
    schedule = f"/api/v1/teams/{graph['team']['id']}/meetings"
    meeting = client.post(schedule, headers=headers, json={
        "title": "Demo", "starts_at": "2099-01-01T12:00:00Z"
    }).json()
    assert meeting["ktalk_url"] is None
    path = f"/api/v1/meetings/{meeting['id']}/ktalk-room"
    assert client.put(path).status_code == 401
    settings = get_settings()
    monkeypatch.setattr(settings, "ktalk_space", "")
    assert client.put(path, headers=headers).status_code == 503
    monkeypatch.setattr(settings, "ktalk_space", "example")
    monkeypatch.setattr(settings, "ktalk_api_key", SecretStr("test-key"))
    calls = []

    def put(url, **kwargs):
        calls.append(url)
        assert url.startswith("https://example.ktalk.ru/api/Rooms/")
        assert kwargs["headers"]["X-Auth-Token"] == "test-key"
        assert kwargs["json"] == {"title": "Demo"}
        if len(calls) == 1:
            raise httpx.ReadTimeout("lost response")
        return httpx.Response(200, request=httpx.Request("PUT", url),
                              json={"roomName": url.rsplit("/", 1)[1]})

    monkeypatch.setattr("app.ktalk.httpx.put", put)
    assert client.put(path, headers=headers).status_code == 504
    assert client.get(schedule + "/next", headers=headers).json()["ktalk_url"] is None
    result = client.put(path, headers=headers)
    assert result.status_code == 200
    assert result.json()["ktalk_url"] == calls[0].replace("/api/Rooms/", "/")
    assert client.put(path, headers=headers).json() == result.json()
    assert calls == [calls[0], calls[0]]
    assert client.get(schedule + "/next", headers=headers).json() == result.json()
