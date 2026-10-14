import time

from tests.test_attempts import PROGRESS, finish, shift, start

COURSE = "/api/v1/course"


async def finish_with(student, attempt, answers_by_index):
    """Завершает попытку с заданными ответами: порядок вопросов в попытке случайный, поэтому ищем по тексту."""
    payload = [
        {"id": item["id"], "student_answer": answers_by_index[item["text_question"]]}
        for item in attempt["result_test"]
    ]
    response = await student.post(f"{PROGRESS}/{attempt['id']}/completion-test", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


async def scenario(world):
    """Alice сдала на 100%, Bob ответил верно только на первый вопрос (50%)."""
    alice, bob = world["alice"], world["bob"]
    await finish(alice, await start(alice, world))
    failed = await finish_with(
        bob, await start(bob, world), {"Вопрос 1": "да", "Вопрос 2": "нет"}
    )
    return failed


async def test_course_analytics_summary(world):
    await scenario(world)
    response = await world["teacher"].get(f"{COURSE}/{world['course_id']}/analytics")
    assert response.status_code == 200
    data = response.json()

    assert data["students_total"] == 2 and data["finished_total"] == 1
    assert data["stalled_total"] == 0 and data["avg_progress_percent"] == 50

    section = data["sections"][0]
    assert (section["reached"], section["passed"], section["tests_count"]) == (2, 1, 1)

    test = data["tests"][0]
    assert (test["passed"], test["attempted"], test["waiting"]) == (1, 2, 0)
    assert test["avg_best_percent"] == 75 and test["avg_attempts_to_pass"] == 1.0

    # Сначала те, кому нужно внимание: активные раньше закончивших.
    by_email = [row["student"]["email"] for row in data["students"]]
    assert by_email == ["bob@test.dev", "alice@test.dev"]
    alice = next(row for row in data["students"] if row["student"]["email"] == "alice@test.dev")
    assert alice["status"] == "finished" and alice["avg_best_percent"] == 100
    assert alice["sections_passed"] == 1 and alice["sections_total"] == 1


async def test_old_unfinished_students_are_stalled(world):
    failed = await scenario(world)
    await shift(failed["id"], finished_at=int(time.time()) - 10 * 86400)

    data = (await world["teacher"].get(f"{COURSE}/{world['course_id']}/analytics")).json()
    statuses = {row["student"]["email"]: row["status"] for row in data["students"]}
    assert statuses == {"bob@test.dev": "stalled", "alice@test.dev": "finished"}
    assert data["stalled_total"] == 1


async def test_empty_course_analytics(world):
    response = await world["teacher"].post(
        f"{COURSE}/", data={"name": "Пустой", "description": "Без студентов"}
    )
    data = (await world["teacher"].get(f"{COURSE}/{response.json()['id']}/analytics")).json()
    assert data["students_total"] == 0 and data["avg_progress_percent"] == 0
    assert data["students"] == [] and data["tests"] == [] and data["sections"] == []


async def test_test_analytics_questions_and_distribution(world):
    await scenario(world)
    url = f"{COURSE}/{world['course_id']}/tests/{world['test_id']}/analytics"
    data = (await world["teacher"].get(url)).json()

    assert data["attempts_total"] == 2 and data["students_attempted"] == 2
    assert data["pass_rate_percent"] == 50 and data["avg_percent"] == 75

    hardest = data["questions"][0]
    assert hardest["text"] == "Вопрос 2" and hardest["correct_percent"] == 50
    assert hardest["top_wrong"] == "нет" and hardest["top_wrong_count"] == 1
    assert data["questions"][1]["correct_percent"] == 100 and data["questions"][1]["top_wrong"] is None

    counts = {bucket["label"]: bucket["count"] for bucket in data["distribution"]}
    assert counts["80–100%"] == 1 and counts["40–59%"] == 1 and sum(counts.values()) == 2
    assert data["avg_duration_seconds"] is not None and data["timed_out"] == 0


async def test_timed_out_attempts_are_counted(world):
    alice = world["alice"]
    attempt = await start(alice, world)
    await shift(attempt["id"], attempt_date=int(time.time()) - 5 * 3600)
    data = (
        await world["teacher"].get(f"{COURSE}/{world['course_id']}/tests/{world['test_id']}/analytics")
    ).json()
    assert data["attempts_total"] == 1 and data["timed_out"] == 1 and data["pass_rate_percent"] == 0


async def test_analytics_access_and_missing_test(world):
    base = f"{COURSE}/{world['course_id']}"
    assert (await world["alice"].get(f"{base}/analytics")).status_code == 403
    assert (await world["alice"].get(f"{base}/tests/{world['test_id']}/analytics")).status_code == 403
    assert (await world["teacher"].get(f"{base}/tests/9999/analytics")).status_code == 404


async def test_student_without_attempts_is_new(world):
    data = (await world["teacher"].get(f"{COURSE}/{world['course_id']}/analytics")).json()
    assert {row["status"] for row in data["students"]} == {"new"}
    assert data["tests"][0]["avg_best_percent"] is None


async def view(student, world, material_id):
    return await student.post(f"{COURSE}/{world['course_id']}/materials/{material_id}/view")


async def add_material(world, title="Лекция"):
    response = await world["teacher"].post(
        f"{COURSE}/{world['course_id']}/materials",
        data={"title": title, "description": "Текст", "section_id": world["section_id"]},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_material_views_count_as_activity(world):
    first = await add_material(world, "Первая")
    await add_material(world, "Вторая")
    alice = world["alice"]

    assert (await view(alice, world, first)).status_code == 204
    assert (await view(alice, world, first)).status_code == 204  # повторный просмотр не дублирует

    data = (await world["teacher"].get(f"{COURSE}/{world['course_id']}/analytics")).json()
    rows = {row["student"]["email"]: row for row in data["students"]}
    assert (rows["alice@test.dev"]["materials_viewed"], rows["alice@test.dev"]["materials_total"]) == (1, 2)
    # Читающий студент уже не «новый», даже если тестов ещё не было.
    assert rows["alice@test.dev"]["status"] == "active" and rows["alice@test.dev"]["last_activity_at"]
    assert rows["bob@test.dev"]["status"] == "new" and rows["bob@test.dev"]["materials_viewed"] == 0


async def test_material_view_rules(world):
    material = await add_material(world)
    teacher = world["teacher"]
    # Преподаватель материал не «просматривает»: запрос принимается и ничего не записывает.
    assert (await view(teacher, world, material)).status_code == 204
    data = (await teacher.get(f"{COURSE}/{world['course_id']}/analytics")).json()
    assert all(row["materials_viewed"] == 0 for row in data["students"])
    # Материала нет в курсе.
    assert (await view(world["alice"], world, 99999)).status_code == 404


async def test_old_activity_with_fresh_reading_is_not_stalled(world):
    failed = await scenario(world)
    await shift(failed["id"], finished_at=int(time.time()) - 10 * 86400)
    material = await add_material(world)
    await view(world["bob"], world, material)

    data = (await world["teacher"].get(f"{COURSE}/{world['course_id']}/analytics")).json()
    statuses = {row["student"]["email"]: row["status"] for row in data["students"]}
    # Bob неделями не проходил тесты, но сегодня читал материал: он занимается.
    assert statuses["bob@test.dev"] == "active"


async def test_csv_exports(world):
    await scenario(world)
    teacher = world["teacher"]

    response = await teacher.get(f"{COURSE}/{world['course_id']}/analytics/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    lines = text.lstrip("﻿").strip().split("\r\n")
    assert lines[0].split(";")[0] == "Студент" and len(lines) == 3
    assert any("alice@test.dev" in line and "Прошёл курс" in line for line in lines)

    tests = await teacher.get(f"{COURSE}/{world['course_id']}/tests/{world['test_id']}/export")
    assert tests.status_code == 200
    rows = tests.content.decode("utf-8").lstrip("﻿").strip().split("\r\n")
    assert len(rows) == 3 and any("Сдан" in row for row in rows)


async def test_csv_exports_are_teacher_only_and_safe(world):
    base = f"{COURSE}/{world['course_id']}"
    assert (await world["alice"].get(f"{base}/analytics/export")).status_code == 403
    assert (await world["alice"].get(f"{base}/tests/{world['test_id']}/export")).status_code == 403
    assert (await world["teacher"].get(f"{base}/tests/9999/export")).status_code == 404


def test_csv_cells_cannot_start_a_formula():
    from api_v1.analytics.export import safe

    assert safe("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert safe("+1") == "'+1" and safe("-1") == "'-1" and safe("@a") == "'@a"
    assert safe("Иван") == "Иван" and safe(None) == "" and safe(5) == "5"


FEED = "/api/v1/activity/students"


async def test_teacher_activity_feed_has_all_kinds(world):
    from tests.conftest import Api

    teacher, alice = world["teacher"], world["alice"]
    material = await add_material(world, "Лекция 1")
    await view(alice, world, material)
    await finish(alice, await start(alice, world))

    # Заявка на курс по заявке.
    course = (
        await teacher.post(
            f"{COURSE}/", data={"name": "По заявке", "description": "О", "enrollment": "request"}
        )
    ).json()["id"]
    carol = await Api(world["transport"]).register("carol@test.dev", world["roles"]["Студент"])
    await carol.post(f"{COURSE}/{course}/apply")

    events = (await teacher.get(FEED)).json()
    kinds = [event["kind"] for event in events]
    assert {"attempt", "material", "application", "invitation_accepted"} <= set(kinds)
    # От новых к старым.
    assert [event["at"] for event in events] == sorted((event["at"] for event in events), reverse=True)

    attempt = next(event for event in events if event["kind"] == "attempt")
    assert attempt["title"] == "Сортировки" and attempt["passed"] is True and attempt["percent"] == 100
    assert attempt["test_id"] == world["test_id"] and attempt["student"]["email"] == "alice@test.dev"
    application = next(event for event in events if event["kind"] == "application")
    assert application["course"]["name"] == "По заявке"


async def test_activity_feed_paging_and_access(world):
    teacher, alice = world["teacher"], world["alice"]
    for number in range(3):
        await view(alice, world, await add_material(world, f"М{number}"))

    first = (await teacher.get(FEED, params={"limit": 2})).json()
    second = (await teacher.get(FEED, params={"limit": 2, "offset": 2})).json()
    assert len(first) == 2 and second
    assert not {event["id"] for event in first} & {event["id"] for event in second}

    assert (await alice.get(FEED)).status_code == 403
    assert (await teacher.get(FEED, params={"limit": 0})).status_code == 422


async def test_feed_shows_only_own_courses(world):
    from tests.conftest import Api

    await finish(world["alice"], await start(world["alice"], world))
    other = await Api(world["transport"]).register("t2@test.dev", world["roles"]["Преподаватель"])
    assert (await other.get(FEED)).json() == []
