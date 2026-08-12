FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY data ./data
COPY scripts ./scripts

RUN pip install --no-cache-dir .

EXPOSE 8080
CMD ["sh", "-c", "alembic upgrade head && eat-what seed-all && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
