from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Account

Db = Annotated[Session, Depends(get_db)]
password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash("dummy-password-for-timing-only")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def create_token(account_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(account_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def unauthorized() -> HTTPException:
    return HTTPException(
        401, "Invalid credentials or expired token", headers={"WWW-Authenticate": "Bearer"}
    )


def current_account(db: Db, token: Annotated[str, Depends(oauth2)]) -> Account:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "iat"]},
        )
        account_id = int(payload["sub"])
        if account_id <= 0 or account_id > 9223372036854775807:
            raise ValueError("Invalid account ID")
    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise unauthorized() from exc
    account = db.get(Account, account_id)
    if account is None or not account.is_active:
        raise unauthorized()
    return account


CurrentAccount = Annotated[Account, Depends(current_account)]


def admin_account(account: CurrentAccount) -> Account:
    if account.system_role != "admin":
        raise HTTPException(403, "Administrator access required")
    return account


AdminAccount = Annotated[Account, Depends(admin_account)]
