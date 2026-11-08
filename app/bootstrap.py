"""Run `python -m app.bootstrap` in the API container to create the first admin."""

from getpass import getpass

from pydantic import ValidationError
from sqlalchemy import select, text

from app.db import SessionLocal
from app.models import Account
from app.schemas import AccountCreate
from app.security import password_hasher


def main():
    try:
        name = input("Full name: ").strip()
        email = input("Email (login): ").strip()
        password = getpass("Password (12+ characters): ")
        if password != getpass("Repeat password: "):
            raise SystemExit("Passwords do not match")
        data = AccountCreate(full_name=name, email=email, password=password, system_role="admin")
    except ValidationError:
        raise SystemExit("Invalid name, email or password (minimum 12 characters)") from None
    with SessionLocal() as db:
        # Serialize first-admin bootstrap even if two commands are started together.
        db.execute(text("SELECT pg_advisory_xact_lock(742019031)"))
        if db.scalar(select(Account.id).where(Account.system_role == "admin", Account.is_active)):
            raise SystemExit("An administrator already exists. Use /auth/register.")
        if db.scalar(select(Account.id).where(Account.email == str(data.email).lower())):
            raise SystemExit("This email already exists")
        db.add(
            Account(
                full_name=data.full_name,
                email=str(data.email).lower(),
                password_hash=password_hasher.hash(data.password),
                system_role="admin",
            )
        )
        db.commit()
    print("Administrator created. Sign in at /docs using your email as username.")


if __name__ == "__main__":
    main()
