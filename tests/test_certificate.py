from tests.test_attempts import finish, start

COURSE = "/api/v1/course"


async def test_certificate_for_finished_student(world):
    alice = world["alice"]
    await finish(alice, await start(alice, world))
    response = await alice.get(f"{COURSE}/{world['course_id']}/certificate")
    assert response.status_code == 200
    data = response.json()
    assert data["course_name"] == "Алгоритмы" and data["student_name"] == "alice@test.dev"
    assert data["teacher_name"] == "teacher@test.dev" and data["finished_at"]
    assert data["number"].startswith(f"ET-{world['course_id']}-{alice.id}-")


async def test_no_certificate_until_course_is_passed(world):
    alice, bob = world["alice"], world["bob"]
    await finish(alice, await start(alice, world), answer="нет")
    assert (await alice.get(f"{COURSE}/{world['course_id']}/certificate")).status_code == 403
    assert (await bob.get(f"{COURSE}/{world['course_id']}/certificate")).status_code == 403


async def test_certificate_is_only_for_students_of_the_course(world):
    # Преподаватель курса сертификата не получает.
    assert (await world["teacher"].get(f"{COURSE}/{world['course_id']}/certificate")).status_code == 403
