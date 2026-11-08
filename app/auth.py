from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select

from app import schemas as s
from app.models import Account
from app.security import (
    DUMMY_HASH,
    AdminAccount,
    CurrentAccount,
    Db,
    create_token,
    password_hasher,
    unauthorized,
)
from app.services import get_or_404, list_records, save

router = APIRouter(tags=["Authentication"])


@router.post("/auth/login", response_model=s.Token)
def login(db: Db, form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if len(form.password) > 128:
        raise unauthorized()
    account = db.scalar(
        select(Account).where(func.lower(Account.email) == form.username.strip().lower())
    )
    valid = password_hasher.verify(form.password, account.password_hash if account else DUMMY_HASH)
    if not valid or account is None or not account.is_active:
        raise unauthorized()
    return s.Token(access_token=create_token(account.id))


@router.get("/auth/me", response_model=s.AccountRead)
def me(account: CurrentAccount):
    return account


@router.post("/auth/register", response_model=s.AccountRead, status_code=201)
def register(payload: s.AccountCreate, db: Db, admin: AdminAccount):
    """Register an employee. Only an administrator can create accounts."""
    account = Account(
        full_name=payload.full_name,
        email=str(payload.email).lower(),
        password_hash=password_hasher.hash(payload.password),
        system_role=payload.system_role,
    )
    return save(db, account)


@router.get("/accounts", response_model=list[s.AccountRead], tags=["Accounts"])
def accounts(
    db: Db,
    account: CurrentAccount,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return list_records(db, Account, offset, limit)


@router.patch("/accounts/{account_id}/access", response_model=s.AccountRead, tags=["Accounts"])
def access(account_id: int, payload: s.AccountAccessUpdate, db: Db, admin: AdminAccount):
    target = get_or_404(db, Account, account_id)
    if target.id == admin.id and (payload.is_active is False or payload.system_role == "curator"):
        raise HTTPException(409, "You cannot disable or demote your own administrator account")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, field, value)
    return save(db, target)
