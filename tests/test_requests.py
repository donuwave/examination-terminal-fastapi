from tests.conftest import Api, join_by_invitation

COURSE = "/api/v1/course"


async def make_course(teacher, enrollment="open", name="Курс"):
    response = await teacher.post(
        f"{COURSE}/", data={"name": name, "description": "Описание", "enrollment": enrollment}
    )
    assert response.status_code == 200
    return response.json()["id"]


async def newcomer(world, email="carol@test.dev"):
    return await Api(world["transport"]).register(email, world["roles"]["Студент"])


async def catalog_entry(user, course_id):
    items = (await user.get(f"{COURSE}/catalog")).json()
    return next(item for item in items if item["id"] == course_id)


async def test_open_course_enrolls_immediately(world):
    carol = await newcomer(world)
    course_id = await make_course(world["teacher"], "open")
    assert (await carol.post(f"{COURSE}/{course_id}/enroll")).status_code == 200
    assert (await catalog_entry(carol, course_id))["is_member"] is True


async def test_request_course_blocks_direct_enroll(world):
    carol = await newcomer(world)
    course_id = await make_course(world["teacher"], "request")

    assert (await carol.post(f"{COURSE}/{course_id}/enroll")).status_code == 403
    entry = await catalog_entry(carol, course_id)
    assert entry["enrollment"] == "request" and entry["is_member"] is False


async def test_apply_and_approve(world):
    teacher, carol = world["teacher"], await newcomer(world)
    course_id = await make_course(teacher, "request")

    applied = await carol.post(f"{COURSE}/{course_id}/apply")
    assert applied.status_code == 201 and applied.json()["kind"] == "application"
    assert (await carol.post(f"{COURSE}/{course_id}/apply")).status_code == 409
    assert (await catalog_entry(carol, course_id))["my_request"] == "application"

    pending = (await teacher.get(f"{COURSE}/{course_id}/requests")).json()
    assert [(item["kind"], item["student"]["email"]) for item in pending] == [
        ("application", "carol@test.dev")
    ]

    approve = await teacher.post(f"{COURSE}/{course_id}/requests/{pending[0]['id']}/approve")
    assert approve.status_code == 200 and approve.json()["status"] == "accepted"

    entry = await catalog_entry(carol, course_id)
    assert entry["is_member"] is True and entry["my_request"] is None
    assert (await teacher.get(f"{COURSE}/{course_id}/requests")).json() == []
    # Повторно обработать уже закрытую заявку нельзя.
    again = await teacher.post(f"{COURSE}/{course_id}/requests/{pending[0]['id']}/approve")
    assert again.status_code == 404


async def test_reject_and_reapply(world):
    teacher, carol = world["teacher"], await newcomer(world)
    course_id = await make_course(teacher, "request")
    await carol.post(f"{COURSE}/{course_id}/apply")
    request_id = (await teacher.get(f"{COURSE}/{course_id}/requests")).json()[0]["id"]

    rejected = await teacher.post(f"{COURSE}/{course_id}/requests/{request_id}/reject")
    assert rejected.json()["status"] == "declined"
    assert (await catalog_entry(carol, course_id))["is_member"] is False
    assert (await carol.post(f"{COURSE}/{course_id}/apply")).status_code == 201


async def test_student_can_cancel_application(world):
    carol = await newcomer(world)
    course_id = await make_course(world["teacher"], "request")
    await carol.post(f"{COURSE}/{course_id}/apply")

    assert (await carol.delete(f"{COURSE}/{course_id}/apply")).status_code == 204
    assert (await world["teacher"].get(f"{COURSE}/{course_id}/requests")).json() == []
    assert (await carol.delete(f"{COURSE}/{course_id}/apply")).status_code == 404


async def test_apply_is_not_for_open_courses(world):
    carol = await newcomer(world)
    course_id = await make_course(world["teacher"], "open")
    assert (await carol.post(f"{COURSE}/{course_id}/apply")).status_code == 400


async def test_invitation_accept_and_decline(world):
    teacher = world["teacher"]
    carol, dave = await newcomer(world), await newcomer(world, "dave@test.dev")
    course_id = await make_course(teacher, "request")

    for student in (carol, dave):
        email = (await student.get("/api/v1/profile/me")).json()["email"]
        sent = await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": email})
        assert sent.status_code == 201

    # Дубль приглашения и приглашение от чужого лица не проходят.
    assert (
        await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "carol@test.dev"})
    ).status_code == 409

    mine = (await carol.get("/api/v1/invitations/")).json()
    assert len(mine) == 1 and mine[0]["course"]["id"] == course_id
    assert mine[0]["course"]["teacher"]["email"] == "teacher@test.dev"
    assert (await catalog_entry(carol, course_id))["my_request"] == "invitation"

    # Чужое приглашение принять нельзя.
    assert (await dave.post(f"/api/v1/invitations/{mine[0]['id']}/accept")).status_code == 404

    assert (await carol.post(f"/api/v1/invitations/{mine[0]['id']}/accept")).status_code == 200
    assert (await catalog_entry(carol, course_id))["is_member"] is True
    assert (await carol.get("/api/v1/invitations/")).json() == []

    theirs = (await dave.get("/api/v1/invitations/")).json()
    assert (await dave.post(f"/api/v1/invitations/{theirs[0]['id']}/decline")).status_code == 200
    assert (await catalog_entry(dave, course_id))["is_member"] is False


async def test_invitation_errors(world):
    teacher, alice = world["teacher"], world["alice"]
    course_id = world["course_id"]

    unknown = await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "nobody@test.dev"})
    assert unknown.status_code == 404
    # Преподавателя приглашать нельзя: ищем только среди студентов.
    other = await Api(world["transport"]).register("t2@test.dev", world["roles"]["Преподаватель"])
    assert (
        await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "t2@test.dev"})
    ).status_code == 404
    # Студент уже на курсе.
    assert (
        await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "alice@test.dev"})
    ).status_code == 400
    # Студент и чужой преподаватель не распоряжаются заявками и приглашениями курса.
    assert (
        await alice.post(f"{COURSE}/{course_id}/invite", json={"email": "bob@test.dev"})
    ).status_code == 403
    assert (await other.get(f"{COURSE}/{course_id}/requests")).status_code == 403
    assert (await alice.get(f"{COURSE}/{course_id}/requests")).status_code == 403


async def test_teacher_can_cancel_invitation_but_not_via_reject(world):
    teacher, carol = world["teacher"], await newcomer(world)
    course_id = await make_course(teacher, "request")
    await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "carol@test.dev"})
    request_id = (await teacher.get(f"{COURSE}/{course_id}/requests")).json()[0]["id"]

    assert (await teacher.post(f"{COURSE}/{course_id}/requests/{request_id}/approve")).status_code == 400
    assert (await teacher.delete(f"{COURSE}/{course_id}/requests/{request_id}")).status_code == 204
    assert (await carol.get("/api/v1/invitations/")).json() == []


async def test_pending_application_blocks_invitation_and_back(world):
    teacher, carol = world["teacher"], await newcomer(world)
    course_id = await make_course(teacher, "request")
    await carol.post(f"{COURSE}/{course_id}/apply")

    blocked = await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "carol@test.dev"})
    assert blocked.status_code == 409 and "одобрите" in blocked.json()["detail"]


async def test_teacher_changes_enrollment_mode(world):
    teacher, course_id = world["teacher"], world["course_id"]
    response = await teacher.patch(f"{COURSE}/{course_id}", json={"enrollment": "request"})
    assert response.status_code == 200 and response.json()["enrollment"] == "request"
    # Пустое значение режим не сбрасывает.
    again = await teacher.patch(f"{COURSE}/{course_id}", json={"enrollment": None, "name": "Новое"})
    assert again.json()["enrollment"] == "request" and again.json()["name"] == "Новое"


async def test_students_cannot_be_added_directly(world):
    response = await world["teacher"].post(
        f"{COURSE}/{world['course_id']}/add_student", json=[world["alice"].id]
    )
    assert response.status_code in (404, 405)


async def test_catalog_is_paged_and_reports_total(world):
    teacher, alice = world["teacher"], world["alice"]
    for number in range(5):
        await teacher.post(f"{COURSE}/", data={"name": f"Курс {number}", "description": "Описание"})

    first = await alice.get(f"{COURSE}/catalog", params={"limit": 2})
    assert first.headers["x-total-count"] == "6" and len(first.json()) == 2
    second = await alice.get(f"{COURSE}/catalog", params={"limit": 2, "offset": 2})
    assert len(second.json()) == 2
    names = [item["name"] for item in first.json() + second.json()]
    assert names == sorted(names) and len(set(names)) == 4

    # Счётчик считает уже отфильтрованное: по «Курс 3» подходит один курс из шести.
    found = await alice.get(f"{COURSE}/catalog", params={"search": "Курс 3", "limit": 1})
    assert found.headers["x-total-count"] == "1" and len(found.json()) == 1
    assert (await alice.get(f"{COURSE}/catalog", params={"limit": 0})).status_code == 422


async def test_course_with_student_attempts_can_be_deleted(world):
    from tests.test_attempts import finish, start

    alice = world["alice"]
    await finish(alice, await start(alice, world))

    response = await world["teacher"].delete(f"{COURSE}/{world['course_id']}")
    assert response.status_code == 200
    # Курс и попытки в нём исчезли, остальное у студента на месте.
    assert (await alice.get("/api/v1/test-progress/")).json() == []
    assert (await alice.get("/api/v1/profile/me")).status_code == 200
