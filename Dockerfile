FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install --no-cache-dir poetry==1.8.5

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root

COPY . .

# Ключи JWT и загруженные файлы подключаются томами, в образ они не попадают.
RUN mkdir -p /app/uploads /app/certs

EXPOSE 8000

# За обратным прокси берём настоящий адрес клиента из X-Forwarded-For: на нём держатся лимиты входа.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
