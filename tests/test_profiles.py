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


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


async def test_registration_date_is_shown(world):
    me = (await world["alice"].get(f"{PROFILE}/me")).json()
    assert me["created_at"]
    card = (await world["teacher"].get(f"{PROFILE}/{world['alice'].id}")).json()
    assert isinstance(card["created_at"], int) and card["created_at"] > 0


async def test_age_and_gender_are_seen_only_by_owner_and_teacher(world):
    alice, bob, teacher = world["alice"], world["bob"], world["teacher"]
    await alice.patch(f"{PROFILE}/", json={"age": 21, "gender": 1})

    own = (await alice.get(f"{PROFILE}/{alice.id}")).json()
    assert (own["age"], own["gender"]) == (21, 1)
    assert (await teacher.get(f"{PROFILE}/{alice.id}")).json()["age"] == 21
    # Однокурсник возраст и пол не видит.
    seen = (await bob.get(f"{PROFILE}/{alice.id}")).json()
    assert seen["age"] is None and seen["gender"] is None


async def test_avatar_upload_visibility_and_removal(world, tmp_path, monkeypatch):
    from api_v1.profile import avatar

    monkeypatch.setattr(avatar, "UPLOAD_DIR", tmp_path)
    alice, bob = world["alice"], world["bob"]
    carol = await stranger(world)

    uploaded = await alice.post(f"{PROFILE}/avatar", files={"file": ("a.png", PNG, "image/png")})
    assert uploaded.status_code == 200 and uploaded.json()["has_avatar"] is True
    assert len(list(tmp_path.iterdir())) == 1

    image = await bob.get(f"{PROFILE}/{alice.id}/avatar")
    assert image.status_code == 200 and image.content == PNG
    assert (await bob.get(f"{PROFILE}/{alice.id}")).json()["has_avatar"] is True
    # Постороннему профиль, а значит и картинка, недоступны.
    assert (await carol.get(f"{PROFILE}/{alice.id}/avatar")).status_code == 404

    # Новая картинка заменяет старую файл.
    await alice.post(f"{PROFILE}/avatar", files={"file": ("b.png", PNG + b"1", "image/png")})
    assert len(list(tmp_path.iterdir())) == 1

    assert (await alice.delete(f"{PROFILE}/avatar")).status_code == 204
    assert list(tmp_path.iterdir()) == []
    assert (await bob.get(f"{PROFILE}/{alice.id}/avatar")).status_code == 404


async def test_avatar_rejects_non_images_and_big_files(world, tmp_path, monkeypatch):
    from api_v1.profile import avatar

    monkeypatch.setattr(avatar, "UPLOAD_DIR", tmp_path)
    alice = world["alice"]
    fake = await alice.post(f"{PROFILE}/avatar", files={"file": ("a.png", b"<html>", "image/png")})
    assert fake.status_code == 400
    big = await alice.post(
        f"{PROFILE}/avatar", files={"file": ("a.png", PNG + b"0" * avatar.MAX_SIZE, "image/png")}
    )
    assert big.status_code == 413
    assert list(tmp_path.iterdir()) == []
