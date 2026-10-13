import os

# Тесты никогда не должны ходить в рабочую базу: адрес берём отдельно и до импорта приложения.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:qwerty@localhost:5438/test_db"
)
if not TEST_DATABASE_URL.rsplit("/", 1)[-1].startswith("test"):
    raise RuntimeError("TEST_DATABASE_URL должен указывать на базу, имя которой начинается с test")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402

from core.models import Role, db_helper  # noqa: E402
from core.rate_limit import login_limiter, registration_limiter  # noqa: E402
from main import app  # noqa: E402
from tests.test_db import TestSessionLocal, get_test_db, recreate_schema, test_engine  # noqa: E402

app.dependency_overrides[db_helper.scoped_session_dependency] = get_test_db

PASSWORD = "secret123"


class Api:
    """Тонкая обёртка: свой клиент и токен на каждого пользователя."""

    def __init__(self, transport: httpx.ASGITransport):
        self.client = httpx.AsyncClient(transport=transport, base_url="http://test")
        self.id: int | None = None

    async def register(self, email: str, role_id: int):
        response = await self.client.post(
            "/api/v1/auth/registration",
            data={"email": email, "role_id": role_id, "password": PASSWORD},
        )
        assert response.status_code == 200, response.text
        self.client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
        self.id = (await self.client.get("/api/v1/profile/me")).json()["id"]
        return self

    def __getattr__(self, name):
        return getattr(self.client, name)


@pytest_asyncio.fixture(autouse=True)
async def database():
    await recreate_schema()
    # Роли в рабочей базе создаёт миграция; в тестовой схеме без миграций кладём их сами.
    async with TestSessionLocal() as session:
        session.add_all([Role(name="Преподаватель"), Role(name="Студент")])
        await session.commit()
    login_limiter.reset()
    registration_limiter.reset()
    yield
    await test_engine.dispose()


@pytest_asyncio.fixture
async def world():
    """Преподаватель с курсом, разделом, тестом на 2 вопроса и два записанных студента."""
    transport = httpx.ASGITransport(app=app)
    anon = httpx.AsyncClient(transport=transport, base_url="http://test")
    roles = {item["name"]: item["id"] for item in (await anon.get("/api/v1/role/")).json()}

    teacher = await Api(transport).register("teacher@test.dev", roles["Преподаватель"])
    alice = await Api(transport).register("alice@test.dev", roles["Студент"])
    bob = await Api(transport).register("bob@test.dev", roles["Студент"])

    course = (
        await teacher.post(
            "/api/v1/course/", data={"name": "Алгоритмы", "description": "Курс для проверки"}
        )
    ).json()
    course_id = course["id"]

    test = (
        await teacher.post(
            "/api/v1/tests/",
            data={
                "name_test": "Сортировки",
                "time_limit": 600,
                "pass_percent": 60,
                "max_attempts": 2,
                "retry_delay_minutes": 120,
            },
        )
    ).json()
    test_id = test["id"]
    questions = [
        {"text_question": f"Вопрос {n}", "options": ["да", "нет"], "correct_answer": "да"}
        for n in (1, 2)
    ]
    assert (
        await teacher.post(f"/api/v1/tests/{test_id}/add_questions", json=questions)
    ).status_code == 200

    section = await teacher.post(f"/api/v1/course/{course_id}/sections", json={"title": "Основы"})
    section_id = section.json()["id"]
    assert (
        await teacher.post(f"/api/v1/course/{course_id}/sections/{section_id}/tests", json=[test_id])
    ).status_code == 204
    assert (
        await teacher.post(f"/api/v1/course/{course_id}/add_student", json=[alice.id, bob.id])
    ).status_code == 200

    yield {
        "teacher": teacher,
        "alice": alice,
        "bob": bob,
        "course_id": course_id,
        "test_id": test_id,
        "section_id": section_id,
        "roles": roles,
        "transport": transport,
    }
    await anon.aclose()
