FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt constraints.txt ./
RUN pip install -r requirements.txt
RUN useradd --create-home appuser
COPY alembic.ini .
COPY migrations migrations
COPY app app
USER appuser

FROM base AS test
USER root
COPY requirements-dev.txt pyproject.toml ./
RUN pip install -r requirements-dev.txt
COPY tests tests
USER appuser
CMD ["pytest", "-q", "-p", "no:cacheprovider"]

FROM base AS runtime
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

