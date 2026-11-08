from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.auth import router as auth_router
from app.resources import router as resource_router
from app.security import Db

app = FastAPI(
    title="Practicum Hub API",
    version="0.1.0",
    description="Internal API for employees managing student project practicums. Students have no accounts.",
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(resource_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
def health(db: Db):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "ok"}
