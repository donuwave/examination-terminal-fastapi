from tests.conftest import Api, join_by_invitation
from tests.test_attempts import finish, start

PROFILE = "/api/v1/profile"


async def stranger(world, email="carol@test.dev"):
    return await Api(world["transport"]).register(email, world["roles"]["Студент"])


async def other_teacher(world):
    return await Api(world["transport"]).register("teacher2@test.dev", world["roles"]["Преподаватель"])


async def test_owner_sees_full_profile(world):
    alice = world["alice"]
    data = (await alice.get(f"{PROFILE}/{alice.id}")).json()
    assert data["email"] == "alice@test.dev" and data["role"] == "Студент"


async def test_teacher_sees_own_student_with_email(world):
    data = (await world["teacher"].get(f"{PROFILE}/{world['alice'].id}")).json()
    assert data["email"] == "alice@test.dev"


async def test_everyone_sees_teacher_without_email(world):
    for viewer in (world["alice"], await other_teacher(world)):
        response = await viewer.get(f"{PROFILE}/{world['teacher'].id}")
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "Преподаватель" and "email" not in data


async def test_classmate_sees_name_only(world):
    data = (await world["alice"].get(f"{PROFILE}/{world['bob'].id}")).json()
    assert "email" not in data and data["role"] == "Студент"


async def test_unrelated_profiles_are_hidden_as_not_found(world):
    carol = await stranger(world)
    t2 = await other_teacher(world)
    # Посторонний студент, чужой преподаватель и сам студент не видят того, с кем ничего не связывает.
    assert (await carol.get(f"{PROFILE}/{world['alice'].id}")).status_code == 404
    assert (await t2.get(f"{PROFILE}/{world['alice'].id}")).status_code == 404
    assert (await world["alice"].get(f"{PROFILE}/{carol.id}")).status_code == 404
    assert (await world["teacher"].get(f"{PROFILE}/{carol.id}")).status_code == 404
    # Несуществующий профиль даёт тот же ответ, по нему нельзя перебирать пользователей.
    assert (await world["alice"].get(f"{PROFILE}/99999")).status_code == 404
    assert (await world["alice"].get(f"{PROFILE}/99999/courses")).status_code == 404


async def test_me_and_password_routes_are_not_shadowed(world):
    assert (await world["alice"].get(f"{PROFILE}/me")).status_code == 200


async def test_teacher_sees_progress_only_in_own_courses(world):
    alice, teacher = world["alice"], world["teacher"]
    await finish(alice, await start(alice, world))

    # Alice учится ещё и у другого преподавателя.
    t2 = await other_teacher(world)
    foreign = (
        await t2.post("/api/v1/course/", data={"name": "Чужой курс", "description": "Описание"})
    ).json()["id"]
    await join_by_invitation(t2, alice, foreign)

    mine = (await teacher.get(f"{PROFILE}/{alice.id}/courses")).json()
    assert mine["total"] == 1 and [c["name"] for c in mine["courses"]] == ["Алгоритмы"]
    course = mine["courses"][0]
    assert (course["sections_passed"], course["sections_total"]) == (1, 1)
    assert course["avg_best_percent"] == 100 and course["students_count"] == 2

    own = (await alice.get(f"{PROFILE}/{alice.id}/courses")).json()
    assert own["total"] == 2 and all(item["sections_total"] is not None for item in own["courses"])

    # Однокурсник видит только общий курс и без прогресса.
    seen = (await world["bob"].get(f"{PROFILE}/{alice.id}/courses")).json()
    assert [c["name"] for c in seen["courses"]] == ["Алгоритмы"]
    assert seen["courses"][0]["sections_passed"] is None and seen["courses"][0]["avg_best_percent"] is None


async def test_teacher_courses_are_public(world):
    t = world["teacher"]
    await t.post(
        "/api/v1/course/",
        data={"name": "По заявке", "description": "Описание", "enrollment": "request"},
    )
    data = (await world["alice"].get(f"{PROFILE}/{t.id}/courses")).json()
    names = {item["name"]: item for item in data["courses"]}
    assert set(names) == {"Алгоритмы", "По заявке"} and data["total"] == 2
    assert names["По заявке"]["enrollment"] == "request"
    assert names["Алгоритмы"]["sections_total"] is None
    # Alice состоит в «Алгоритмах», но не в курсе «По заявке».
    assert names["Алгоритмы"]["is_member"] is True and names["По заявке"]["is_member"] is False


async def test_profile_courses_paging(world):
    t = world["teacher"]
    for number in range(3):
        await t.post("/api/v1/course/", data={"name": f"Курс {number}", "description": "Описание"})
    page = (await world["alice"].get(f"{PROFILE}/{t.id}/courses", params={"limit": 2})).json()
    assert len(page["courses"]) == 2 and page["total"] == 4
    rest = (
        await world["alice"].get(f"{PROFILE}/{t.id}/courses", params={"limit": 2, "offset": 2})
    ).json()
    assert len(rest["courses"]) == 2
    assert (await world["alice"].get(f"{PROFILE}/{t.id}/courses", params={"limit": 0})).status_code == 422


async def test_teacher_sees_student_activity_in_course_row(world):
    alice, teacher = world["alice"], world["teacher"]
    await finish_attempt(alice, world)
    rows = (await teacher.get(f"{PROFILE}/{alice.id}/courses")).json()["courses"]
    assert rows[0]["last_activity_at"]
    # Однокурсник активность не видит так же, как и прогресс.
    seen = (await world["bob"].get(f"{PROFILE}/{alice.id}/courses")).json()["courses"]
    assert seen[0]["last_activity_at"] is None


async def finish_attempt(student, world):
    await finish(student, await start(student, world))
