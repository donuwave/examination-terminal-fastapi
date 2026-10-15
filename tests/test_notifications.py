import time

from api_v1.notification.jobs import cleanup_notifications, notify_pause_over
from tests.conftest import Api
from tests.test_attempts import PROGRESS, finish, shift, start
from tests.test_db import TestSessionLocal

NOTES = "/api/v1/notifications"
COURSE = "/api/v1/course"


async def notes(user):
    return (await user.get(f"{NOTES}/")).json()


async def kinds(user):
    return [item["kind"] for item in await notes(user)]


async def newcomer(world, email="carol@test.dev"):
    return await Api(world["transport"]).register(email, world["roles"]["Студент"])


async def request_course(teacher):
    response = await teacher.post(
        f"{COURSE}/", data={"name": "По заявке", "description": "Описание", "enrollment": "request"}
    )
    return response.json()["id"]


async def test_invitation_flow_notifies_both_sides(world):
    teacher, carol = world["teacher"], await newcomer(world)
    course_id = await request_course(teacher)

    invite = await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "carol@test.dev"})
    assert await kinds(carol) == ["invitation"]
    item = (await notes(carol))[0]
    assert "По заявке" in item["text"] and item["read_at"] is None and item["link"] == "/"

    await carol.post(f"/api/v1/invitations/{invite.json()['id']}/accept")
    teacher_notes = await notes(teacher)
    assert teacher_notes[0]["kind"] == "invitation_answered"
    assert "принял" in teacher_notes[0]["text"]


async def test_application_flow_notifies_both_sides(world):
    teacher, carol = world["teacher"], await newcomer(world)
    course_id = await request_course(teacher)

    await carol.post(f"{COURSE}/{course_id}/apply")
    # В фикстуре студенты принимали приглашения, поэтому у преподавателя уже есть записи.
    assert (await notes(teacher))[0]["kind"] == "new_application"

    request_id = (await teacher.get(f"{COURSE}/{course_id}/requests")).json()[0]["id"]
    await teacher.post(f"{COURSE}/{course_id}/requests/{request_id}/approve")
    decided = (await notes(carol))[0]
    assert decided["kind"] == "application_decided" and decided["title"] == "Заявка одобрена"
    assert decided["link"] == f"/courses/{course_id}"


async def test_removal_notifies_only_when_teacher_removes(world):
    teacher, alice, bob = world["teacher"], world["alice"], world["bob"]
    course_id = world["course_id"]

    await bob.post(f"{COURSE}/{course_id}/leave")
    assert "removed" not in await kinds(bob)

    await teacher.post(f"{COURSE}/{course_id}/delete_student", params={"student_id": alice.id})
    assert (await notes(alice))[0]["kind"] == "removed"


async def test_attempts_out_and_extra_attempt(world):
    teacher, alice = world["teacher"], world["alice"]

    first = await finish(alice, await start(alice, world), answer="нет")
    assert "attempts_out" not in await kinds(teacher)
    await shift(first["id"], finished_at=int(time.time()) - 3 * 3600)
    await finish(alice, await start(alice, world), answer="нет")

    out = (await notes(teacher))[0]
    assert out["kind"] == "attempts_out" and "Сортировки" in out["text"]
    assert out["link"].endswith(f"/tests/{world['test_id']}/results")
    # Имя студента в тексте можно сделать ссылкой на профиль.
    assert out["actor_id"] == alice.id and out["actor_name"] in out["text"]

    grant = {"course_id": world["course_id"], "test_id": world["test_id"], "student_id": alice.id}
    await teacher.post(f"{PROGRESS}/grant", json=grant)
    assert (await notes(alice))[0]["kind"] == "extra_attempt"


async def test_passing_does_not_ping_teacher(world):
    alice, teacher = world["alice"], world["teacher"]
    await finish(alice, await start(alice, world))
    assert "attempts_out" not in await kinds(teacher)


async def test_read_marks_and_counts(world):
    teacher, carol = world["teacher"], await newcomer(world)
    course_id = await request_course(teacher)
    await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "carol@test.dev"})

    assert (await carol.get(f"{NOTES}/unread-count")).json() == {"count": 1}
    item = (await notes(carol))[0]
    # Чужое уведомление прочитать нельзя.
    assert (await world["alice"].post(f"{NOTES}/{item['id']}/read")).status_code == 404

    assert (await carol.post(f"{NOTES}/{item['id']}/read")).status_code == 204
    assert (await carol.get(f"{NOTES}/unread-count")).json() == {"count": 0}
    assert (await notes(carol))[0]["read_at"] is not None


async def test_read_all_and_paging(world):
    teacher, carol = world["teacher"], await newcomer(world)
    for number in range(3):
        course_id = await request_course(teacher)
        await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "carol@test.dev"})
        await carol.post(f"{COURSE}/{course_id}/apply")  # уже приглашена: дубль, уведомлений не добавит
    assert (await carol.get(f"{NOTES}/unread-count")).json() == {"count": 3}

    page = (await carol.get(f"{NOTES}/", params={"limit": 2})).json()
    assert len(page) == 2 and page[0]["id"] > page[1]["id"]
    rest = (await carol.get(f"{NOTES}/", params={"limit": 2, "offset": 2})).json()
    assert len(rest) == 1

    await carol.post(f"{NOTES}/read-all")
    assert (await carol.get(f"{NOTES}/unread-count")).json() == {"count": 0}
    assert (await carol.get(f"{NOTES}/", params={"limit": 0})).status_code == 422


async def test_disabled_kind_is_not_delivered(world):
    teacher, carol = world["teacher"], await newcomer(world)
    settings = (await carol.get(f"{NOTES}/settings")).json()
    assert settings["invitation"] is True and len(settings) == 9

    changed = await carol.put(f"{NOTES}/settings", json={"kind": "invitation", "enabled": False})
    assert changed.json()["invitation"] is False
    assert (await carol.put(f"{NOTES}/settings", json={"kind": "nope", "enabled": False})).status_code == 422

    course_id = await request_course(teacher)
    await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "carol@test.dev"})
    assert await kinds(carol) == []
    # Само приглашение при этом создано: отключается только уведомление.
    assert len((await carol.get("/api/v1/invitations/")).json()) == 1


async def run_job() -> int:
    async with TestSessionLocal() as session:
        return await notify_pause_over(session)


async def test_pause_over_is_sent_once(world):
    alice = world["alice"]
    failed = await finish(alice, await start(alice, world), answer="нет")

    # Пауза ещё идёт: ничего не отправляем.
    assert await run_job() == 0

    await shift(failed["id"], finished_at=int(time.time()) - 3 * 3600)
    assert await run_job() == 1
    item = (await notes(alice))[0]
    assert item["kind"] == "pause_over" and "Сортировки" in item["text"]
    assert await run_job() == 0


async def test_pause_over_skipped_when_retaken_or_passed(world):
    alice, bob = world["alice"], world["bob"]

    # Alice уже пересдала: напоминать не о чем.
    first = await finish(alice, await start(alice, world), answer="нет")
    await shift(first["id"], finished_at=int(time.time()) - 3 * 3600)
    await start(alice, world)
    # Bob сдал с первой попытки.
    await finish(bob, await start(bob, world))

    assert await run_job() == 0
    assert "pause_over" not in await kinds(alice) + await kinds(bob)


async def test_teacher_is_told_when_student_finishes_course(world):
    alice, teacher = world["alice"], world["teacher"]
    await finish(alice, await start(alice, world))
    item = next(n for n in await notes(teacher) if n["kind"] == "course_finished")
    assert "Алгоритмы" in item["text"] and item["link"].endswith("/analytics")
    # Один раз на студента, а не на каждый сданный тест.
    assert sum(1 for n in await notes(teacher) if n["kind"] == "course_finished") == 1


async def test_failing_does_not_finish_course(world):
    alice, teacher = world["alice"], world["teacher"]
    await finish(alice, await start(alice, world), answer="нет")
    assert "course_finished" not in await kinds(teacher)


async def test_old_notifications_are_cleaned_up(world):
    from datetime import datetime, timedelta

    from sqlalchemy import update

    from core.models import Notification

    alice = world["alice"]
    teacher = world["teacher"]
    carol = await newcomer(world)
    course_id = await request_course(teacher)
    await teacher.post(f"{COURSE}/{course_id}/invite", json={"email": "carol@test.dev"})
    await carol.post(f"{NOTES}/read-all")
    await alice.post(f"{NOTES}/read-all")

    old = datetime.now() - timedelta(days=120)
    async with TestSessionLocal() as session:
        await session.execute(
            update(Notification).where(Notification.user_id == alice.id).values(read_at=old, created_at=old)
        )
        await session.commit()
    async with TestSessionLocal() as session:
        removed = await cleanup_notifications(session)

    assert removed >= 1
    assert await notes(alice) == []
    # Свежие прочитанные уведомления остаются.
    assert len(await notes(carol)) == 1
