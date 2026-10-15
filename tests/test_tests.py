from tests.conftest import Api
from tests.test_attempts import finish, start

TESTS = "/api/v1/tests"


async def second_teacher(world):
    return await Api(world["transport"]).register("teacher2@test.dev", world["roles"]["Преподаватель"])


async def test_author_updates_settings(world):
    teacher, test_id = world["teacher"], world["test_id"]
    response = await teacher.patch(
        f"{TESTS}/{test_id}", json={"name": "Сортировки 2", "pass_percent": 80, "time_limit": 900}
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["pass_percent"], body["time_limit"]) == ("Сортировки 2", 80, 900)
    assert body["max_attempts"] == 2  # не переданное не трогаем


async def test_invalid_settings_are_rejected(world):
    teacher, test_id = world["teacher"], world["test_id"]
    for bad in ({"pass_percent": 0}, {"max_attempts": 11}, {"name": ""}, {"time_limit": 0}):
        assert (await teacher.patch(f"{TESTS}/{test_id}", json=bad)).status_code == 422


async def test_only_author_sees_and_changes_test(world):
    test_id = world["test_id"]
    other = await second_teacher(world)

    # Правильные ответы не должны утекать ни студентам, ни чужим преподавателям.
    for user in (world["alice"], other):
        assert (await user.get(f"{TESTS}/{test_id}")).status_code == 403
        assert (await user.patch(f"{TESTS}/{test_id}", json={"name": "x"})).status_code == 403
        assert (await user.delete(f"{TESTS}/{test_id}")).status_code == 403
    assert (await world["teacher"].get(f"{TESTS}/{test_id}")).status_code == 200


async def test_question_edit_and_delete(world):
    teacher, test_id = world["teacher"], world["test_id"]
    questions = (await teacher.get(f"{TESTS}/{test_id}")).json()["questions"]
    first, second = questions[0]["id"], questions[1]["id"]

    edited = await teacher.patch(
        f"{TESTS}/{test_id}/questions/{first}",
        json={"text_question": "  Новый текст  ", "options": ["a", "b", "c"], "correct_answer": "c"},
    )
    assert edited.status_code == 200
    assert edited.json()["text_question"] == "Новый текст"
    assert edited.json()["correct_answer"] == "c"

    # Правильный ответ должен оставаться одним из вариантов.
    broken = await teacher.patch(
        f"{TESTS}/{test_id}/questions/{first}", json={"options": ["a", "b"]}
    )
    assert broken.status_code == 422

    assert (await teacher.delete(f"{TESTS}/{test_id}/questions/{second}")).status_code == 204
    left = (await teacher.get(f"{TESTS}/{test_id}")).json()["questions"]
    assert [item["id"] for item in left] == [first]
    assert (await teacher.delete(f"{TESTS}/{test_id}/questions/{second}")).status_code == 404


async def test_new_questions_are_validated(world):
    teacher, test_id = world["teacher"], world["test_id"]
    bad = [
        {"text_question": "q", "options": ["a"], "correct_answer": "a"},
        {"text_question": "q", "options": ["a", "a"], "correct_answer": "a"},
        {"text_question": "q", "options": ["a", "b"], "correct_answer": "z"},
        {"text_question": " ", "options": ["a", "b"], "correct_answer": "a"},
    ]
    for question in bad:
        assert (await teacher.post(f"{TESTS}/{test_id}/add_questions", json=[question])).status_code == 422


async def test_student_cannot_touch_questions_endpoints(world):
    # Старый открытый /questions удалён: там можно было читать и менять правильные ответы.
    assert (await world["alice"].get("/api/v1/questions/1")).status_code == 404


async def test_test_with_attempts_cannot_be_deleted(world):
    alice = world["alice"]
    await finish(alice, await start(alice, world))
    response = await world["teacher"].delete(f"{TESTS}/{world['test_id']}")
    assert response.status_code == 409


async def test_unused_test_is_deleted_everywhere(world):
    teacher, test_id, course_id = world["teacher"], world["test_id"], world["course_id"]
    assert (await teacher.delete(f"{TESTS}/{test_id}")).status_code == 204

    assert (await teacher.get(f"{TESTS}/{test_id}")).status_code == 404
    assert (await teacher.get(f"{TESTS}/")).json() == []
    sections = (await teacher.get(f"/api/v1/course/{course_id}/sections")).json()
    assert sections[0]["tests"] == []


async def test_new_questions_keep_order_and_return_ids(world):
    teacher, test_id = world["teacher"], world["test_id"]
    added = await teacher.post(
        f"{TESTS}/{test_id}/add_questions",
        json=[
            {"text_question": "Третий", "options": ["a", "b"], "correct_answer": "a"},
            {"text_question": "Четвёртый", "options": ["a", "b"], "correct_answer": "a"},
        ],
    )
    ids = [item["id"] for item in added.json()]
    assert len(ids) == 2
    texts = [q["text_question"] for q in (await teacher.get(f"{TESTS}/{test_id}")).json()["questions"]]
    assert texts == ["Вопрос 1", "Вопрос 2", "Третий", "Четвёртый"]


async def test_questions_can_be_reordered(world):
    teacher, test_id = world["teacher"], world["test_id"]
    questions = (await teacher.get(f"{TESTS}/{test_id}")).json()["questions"]
    ids = [q["id"] for q in questions]

    reordered = await teacher.put(f"{TESTS}/{test_id}/questions/order", json=list(reversed(ids)))
    assert reordered.status_code == 204
    after = (await teacher.get(f"{TESTS}/{test_id}")).json()["questions"]
    assert [q["id"] for q in after] == list(reversed(ids))

    # Нужно передать все вопросы по одному разу.
    for bad in ([ids[0]], ids + ids, [*ids, 99999], []):
        assert (await teacher.put(f"{TESTS}/{test_id}/questions/order", json=bad)).status_code == 422
    # Чужой преподаватель и студент порядок менять не могут.
    other = await second_teacher(world)
    assert (await other.put(f"{TESTS}/{test_id}/questions/order", json=ids)).status_code == 403
    assert (await world["alice"].put(f"{TESTS}/{test_id}/questions/order", json=ids)).status_code == 403
