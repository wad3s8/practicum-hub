from fastapi import HTTPException
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import Base


def get_or_404(db: Session, model: type[Base], item_id: int):
    if item_id <= 0 or item_id > 9223372036854775807:
        raise HTTPException(404, "Record not found")
    item = db.get(model, item_id)
    if item is None:
        raise HTTPException(404, f"{model.__tablename__} not found")
    return item


def save(db: Session, item):
    db.add(item)
    commit(db)
    db.refresh(item)
    return item


def commit(db: Session):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Conflicting data: duplicate record, invalid reference or date range"
        ) from exc


def merged_values(item, patch: BaseModel, full_schema: type[BaseModel]):
    values = {field: getattr(item, field) for field in full_schema.model_fields}
    values.update(patch.model_dump(exclude_unset=True))
    try:
        return full_schema.model_validate(values)
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False, include_input=False)) from exc


def update(db: Session, item, patch: BaseModel, full_schema: type[BaseModel]):
    validated = merged_values(item, patch, full_schema)
    for field, value in validated.model_dump().items():
        setattr(item, field, value)
    return save(db, item)


def delete_unreferenced(db: Session, item):
    db.delete(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Record is used in history and cannot be deleted") from exc


def list_records(db: Session, model: type[Base], offset: int, limit: int, *filters):
    return db.scalars(
        select(model).where(*filters).order_by(model.id).offset(offset).limit(limit)
    ).all()
