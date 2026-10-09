import time

from sqlalchemy import update

from core.models import TestProgress
from tests.test_db import TestSessionLocal

PROGRESS = "/api/v1/test-progress"


async def start(student, world):
    response = await student.post(
        f"{PROGRESS}/start", json={"course_id": world["course_id"], "test_id": world["test_id"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def finish(student, attempt, answer="да"):
    answers = [{"id": item["id"], "student_answer": answer} for item in attempt["result_test"]]
    response = await student.post(f"{PROGRESS}/{attempt['id']}/completion-test", json=answers)
    assert response.status_code == 200, response.text
    return response.json()


async def shift(attempt_id: int, **fields):
    async with TestSessionLocal() as session:
        await session.execute(update(TestProgress).where(TestProgress.id == attempt_id).values(**fields))
        await session.commit()


async def test_passing_first_try(world):
    alice = world["alice"]
    attempt = await start(alice, world)
    assert attempt["status"] == 2 and attempt["attempt_no"] == 1

    done = await finish(alice, attempt)
    assert done["status"] == 3 and done["passed"] is True
    assert done["count_current_answer"] == 2
    assert all(item["is_correct"] for item in done["result_test"])
    # Тест сдан, правильные ответы открыты.
    assert all(item["correct_answer"] == "да" for item in done["result_test"])


async def test_failed_attempt_hides_answers_and_starts_pause(world):
    alice = world["alice"]
    done = await finish(alice, await start(alice, world), answer="нет")

    assert done["passed"] is False and done["count_current_answer"] == 0
    assert all(item["is_correct"] is False for item in done["result_test"])
    assert all(item["correct_answer"] is None for item in done["result_test"])
    assert done["state"]["status"] == "cooldown"

    again = await alice.post(
        f"{PROGRESS}/start", json={"course_id": world["course_id"], "test_id": world["test_id"]}
    )
    assert again.status_code == 400


async def test_retry_after_pause_then_waiting_and_extra_attempt(world):
    alice, teacher = world["alice"], world["teacher"]

    first = await finish(alice, await start(alice, world), answer="нет")
    await shift(first["id"], finished_at=int(time.time()) - 3 * 3600)
    second = await start(alice, world)
    assert second["attempt_no"] == 2
    done = await finish(alice, second, answer="нет")
    assert done["state"]["status"] == "waiting"
    # Попытки кончились: правильные ответы открыты.
    assert all(item["correct_answer"] == "да" for item in done["result_test"])

    grant = {"course_id": world["course_id"], "test_id": world["test_id"], "student_id": alice.id}
    assert (await teacher.post(f"{PROGRESS}/grant", json=grant)).status_code == 204

    # Дополнительная попытка идёт без паузы.
    third = await start(alice, world)
    assert third["attempt_no"] == 3
    assert (await finish(alice, third))["passed"] is True


async def test_grant_requires_exhausted_attempts(world):
    grant = {
        "course_id": world["course_id"],
        "test_id": world["test_id"],
        "student_id": world["alice"].id,
    }
    response = await world["teacher"].post(f"{PROGRESS}/grant", json=grant)
    assert response.status_code == 400


async def test_expired_attempt_is_closed_at_deadline(world):
    alice = world["alice"]
    attempt = await start(alice, world)
    started = int(time.time()) - 5 * 3600
    await shift(attempt["id"], attempt_date=started)

    stored = (await alice.get(f"{PROGRESS}/{attempt['id']}")).json()
    assert stored["status"] == 3 and stored["passed"] is False
    # Закрыта временем окончания, а не моментом, когда студент вернулся.
    assert stored["finished_at"] == started + 600


async def test_expired_attempt_is_closed_by_list_and_stats(world):
    alice = world["alice"]
    attempt = await start(alice, world)
    await shift(attempt["id"], attempt_date=int(time.time()) - 5 * 3600)

    stats = (await alice.get(f"{PROGRESS}/stats")).json()
    assert stats == {"finished": 1, "passed_tests": 0}
    assert (await alice.get(f"{PROGRESS}/")).json()[0]["status"] == 3


async def test_cannot_touch_foreign_attempt(world):
    attempt = await start(world["alice"], world)
    response = await world["bob"].get(f"{PROGRESS}/{attempt['id']}")
    assert response.status_code == 403


async def test_student_not_enrolled_cannot_start(world):
    stranger = await world["bob"].post(
        "/api/v1/auth/registration", data={"email": "x@test.dev", "role_id": 2, "password": "secret123"}
    )
    assert stranger.status_code == 200
    response = await world["bob"].client.post(
        f"{PROGRESS}/start",
        json={"course_id": 999, "test_id": world["test_id"]},
        headers={"Authorization": f"Bearer {stranger.json()['access_token']}"},
    )
    assert response.status_code == 403


async def test_list_is_paged_and_filtered_by_date(world):
    alice = world["alice"]
    old = await finish(alice, await start(alice, world), answer="нет")
    # Первая попытка завершилась сутки назад, пауза после неё прошла.
    await shift(old["id"], finished_at=int(time.time()) - 26 * 3600)
    fresh = await finish(alice, await start(alice, world), answer="нет")

    full = (await alice.get(f"{PROGRESS}/")).json()
    assert [item["id"] for item in full] == [fresh["id"], old["id"]]

    first = (await alice.get(f"{PROGRESS}/", params={"limit": 1})).json()
    assert [item["id"] for item in first] == [fresh["id"]]
    second = (await alice.get(f"{PROGRESS}/", params={"limit": 1, "offset": 1})).json()
    assert [item["id"] for item in second] == [old["id"]]

    now = int(time.time())
    today = (
        await alice.get(f"{PROGRESS}/", params={"finished_from": now - 12 * 3600, "finished_to": now + 1})
    ).json()
    assert [item["id"] for item in today] == [fresh["id"]]

    assert (await alice.get(f"{PROGRESS}/", params={"limit": 0})).status_code == 422
    assert (await alice.get(f"{PROGRESS}/", params={"limit": 500})).status_code == 422


async def test_stats_count_passed_tests_once(world):
    alice = world["alice"]
    await finish(alice, await start(alice, world))
    assert (await alice.get(f"{PROGRESS}/stats")).json() == {"finished": 1, "passed_tests": 1}


async def test_teacher_results_show_every_student(world):
    alice = world["alice"]
    await finish(alice, await start(alice, world))
    response = await world["teacher"].get(
        f"{PROGRESS}/results",
        params={"course_id": world["course_id"], "test_id": world["test_id"]},
    )
    assert response.status_code == 200
    by_email = {row["student"]["email"]: row for row in response.json()}
    assert by_email["alice@test.dev"]["status"] == "passed"
    assert by_email["alice@test.dev"]["best_percent"] == 100
    assert by_email["bob@test.dev"]["status"] == "new"
