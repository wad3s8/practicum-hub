from uuid import UUID

import httpx
from fastapi import HTTPException

from app.config import get_settings


def create_room(key: UUID, title: str) -> str:
    settings = get_settings()
    token = settings.ktalk_api_key.get_secret_value()
    if not settings.ktalk_space or not token:
        raise HTTPException(503, "Configure KTALK_SPACE and KTALK_API_KEY to create a room")

    origin = f"https://{settings.ktalk_space}.ktalk.ru"
    name = key.hex
    try:
        response = httpx.put(
            f"{origin}/api/Rooms/{name}",
            headers={"X-Auth-Token": token},
            json={"title": title},
            timeout=8,
            follow_redirects=False,
        )
        response.raise_for_status()
        room = response.json()
    except httpx.TimeoutException:
        raise HTTPException(504, "Kontur.Talk timed out. Retry this request.") from None
    except (httpx.HTTPError, ValueError):
        raise HTTPException(502, "Kontur.Talk could not confirm the room") from None
    if not isinstance(room, dict) or room.get("roomName") != name:
        raise HTTPException(502, "Kontur.Talk returned an unexpected room")
    return f"{origin}/{name}"
