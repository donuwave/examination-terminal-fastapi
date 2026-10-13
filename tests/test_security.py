from core.rate_limit import registration_limiter
from tests.conftest import PASSWORD, Api
from tests.test_tests import TESTS, second_teacher


async def login(client, email, password):
    return await client.post("/api/v1/auth/login", data={"email": email, "password": password})


async def test_roles_cannot_be_created_over_api(world):
    response = await world["alice"].post("/api/v1/role/", data={"role_name": "Админ"})
    assert response.status_code in (404, 405)
    names = [item["name"] for item in (await world["alice"].get("/api/v1/role/")).json()]
    assert names == ["Преподаватель", "Студент"]


async def test_profiles_list_is_not_public(world):
    response = await world["alice"].get("/api/v1/profile/")
    assert response.status_code in (404, 405)


async def test_cannot_attach_foreign_test_to_own_course(world):
    other = await second_teacher(world)
    course = (
        await other.post("/api/v1/course/", data={"name": "Чужой", "description": "Курс"})
    ).json()
    section = (
        await other.post(f"/api/v1/course/{course['id']}/sections", json={"title": "Раздел"})
    ).json()

    response = await other.post(
        f"/api/v1/course/{course['id']}/sections/{section['id']}/tests",
        json=[world["test_id"]],
    )
    assert response.status_code == 404
    # А свой тест подключается как обычно.
    own = (
        await other.post(
            f"{TESTS}/",
            data={"name_test": "Мой", "time_limit": 600},
        )
    ).json()
    ok = await other.post(
        f"/api/v1/course/{course['id']}/sections/{section['id']}/tests", json=[own["id"]]
    )
    assert ok.status_code == 204


async def test_login_is_blocked_after_repeated_failures(world):
    client = world["alice"].client
    for _ in range(5):
        assert (await login(client, "alice@test.dev", "wrong-password")).status_code == 401

    blocked = await login(client, "alice@test.dev", PASSWORD)
    assert blocked.status_code == 429
    assert "Попробуйте через" in blocked.json()["detail"]
    assert "retry-after" in blocked.headers

    # Другой аккаунт с того же адреса не блокируется.
    assert (await login(client, "bob@test.dev", PASSWORD)).status_code == 200


async def test_successful_login_resets_failures(world):
    client = world["alice"].client
    for _ in range(4):
        await login(client, "alice@test.dev", "wrong-password")
    assert (await login(client, "alice@test.dev", PASSWORD)).status_code == 200
    for _ in range(4):
        assert (await login(client, "alice@test.dev", "wrong-password")).status_code == 401


async def test_registration_is_limited_per_address(world):
    registration_limiter.limit = 3
    try:
        statuses = []
        for number in range(5):
            api = Api(world["transport"])
            response = await api.client.post(
                "/api/v1/auth/registration",
                data={
                    "email": f"new{number}@test.dev",
                    "role_id": world["roles"]["Студент"],
                    "password": PASSWORD,
                },
            )
            statuses.append(response.status_code)
        # В фикстуре world уже зарегистрировано трое, поэтому лимит исчерпан сразу.
        assert statuses[-1] == 429
    finally:
        registration_limiter.limit = 10
