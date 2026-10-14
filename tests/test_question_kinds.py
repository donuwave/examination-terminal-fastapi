from api_v1.test_progress.grading import is_answer_correct, normalize
from tests.test_attempts import PROGRESS, start

TESTS = "/api/v1/tests"


async def make_test(world, questions):
    """Новый тест преподавателя в разделе курса, где студенты уже состоят."""
    teacher = world["teacher"]
    created = (
        await teacher.post(
            f"{TESTS}/",
            data={"name_test": "Типы", "time_limit": 600, "pass_percent": 60, "max_attempts": 3},
        )
    ).json()
    added = await teacher.post(f"{TESTS}/{created['id']}/add_questions", json=questions)
    assert added.status_code == 200, added.text
    attach = await teacher.post(
        f"/api/v1/course/{world['course_id']}/sections/{world['section_id']}/tests", json=[created["id"]]
    )
    assert attach.status_code == 204
    return created["id"]


async def begin(student, world, test_id):
    response = await student.post(
        f"{PROGRESS}/start", json={"course_id": world["course_id"], "test_id": test_id}
    )
    assert response.status_code == 200, response.text
    return response.json()


def by_text(attempt):
    return {item["text_question"]: item for item in attempt["result_test"]}


async def submit(student, attempt, answers):
    """answers: текст вопроса → строка, список или None."""
    payload = []
    for item in attempt["result_test"]:
        value = answers.get(item["text_question"])
        entry = {"id": item["id"]}
        if isinstance(value, list):
            entry["student_answers"] = value
        else:
            entry["student_answer"] = value
        payload.append(entry)
    response = await student.post(f"{PROGRESS}/{attempt['id']}/completion-test", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_grading_rules():
    assert normalize("  Москва   ") == "москва"
    # single
    assert is_answer_correct("single", "a", ["a"], "a", None)
    assert not is_answer_correct("single", "a", ["a"], "b", None)
    # multiple: нужно ровно верное множество
    assert is_answer_correct("multiple", "a", ["a", "c"], None, ["c", "a"])
    assert not is_answer_correct("multiple", "a", ["a", "c"], None, ["a"])
    assert not is_answer_correct("multiple", "a", ["a", "c"], None, ["a", "b", "c"])
    assert not is_answer_correct("multiple", "a", ["a", "c"], None, None)
    # text: регистр и пробелы не важны, допустимо несколько написаний
    assert is_answer_correct("text", "Москва", ["Москва", "Moscow"], " москва ", None)
    assert is_answer_correct("text", "Москва", ["Москва", "Moscow"], "MOSCOW", None)
    assert not is_answer_correct("text", "Москва", ["Москва"], "Питер", None)
    assert not is_answer_correct("text", "Москва", ["Москва"], "   ", None)


async def test_mixed_test_all_kinds_pass(world):
    test_id = await make_test(
        world,
        [
            {"text_question": "Один", "options": ["a", "b"], "correct_answer": "a"},
            {
                "text_question": "Несколько",
                "kind": "multiple",
                "options": ["x", "y", "z"],
                "correct_answers": ["x", "z"],
            },
            {"text_question": "Текст", "kind": "text", "correct_answers": ["Москва", "Moscow"]},
        ],
    )
    alice = world["alice"]
    attempt = await begin(alice, world, test_id)
    items = by_text(attempt)
    assert items["Один"]["kind"] == "single" and items["Несколько"]["kind"] == "multiple"
    assert items["Текст"]["kind"] == "text" and items["Текст"]["options"] == []
    # Пока идёт попытка, верные ответы не раскрыты.
    assert all(item["correct_answers"] is None for item in attempt["result_test"])

    done = await submit(
        alice, attempt, {"Один": "a", "Несколько": ["z", "x"], "Текст": "  moscow "}
    )
    assert done["passed"] is True and done["count_current_answer"] == 3
    assert all(item["is_correct"] for item in done["result_test"])
    # Тест сдан: ответы открыты.
    shown = by_text(done)
    assert sorted(shown["Несколько"]["correct_answers"]) == ["x", "z"]
    assert shown["Несколько"]["student_answers"] is not None


async def test_partial_and_wrong_answers_are_not_correct(world):
    test_id = await make_test(
        world,
        [
            {"text_question": "Несколько", "kind": "multiple", "options": ["x", "y", "z"], "correct_answers": ["x", "z"]},
            {"text_question": "Текст", "kind": "text", "correct_answers": ["Москва"]},
        ],
    )
    bob = world["bob"]
    done = await submit(bob, await begin(bob, world, test_id), {"Несколько": ["x"], "Текст": "Питер"})
    assert done["passed"] is False and done["count_current_answer"] == 0
    # Тест не сдан, попытки ещё есть: верные ответы скрыты, но видно, какие вопросы неверны.
    assert all(item["correct_answers"] is None for item in done["result_test"])
    assert all(item["is_correct"] is False for item in done["result_test"])


async def test_answer_validation_per_kind(world):
    test_id = await make_test(
        world,
        [
            {"text_question": "Несколько", "kind": "multiple", "options": ["x", "y"], "correct_answers": ["x"]},
            {"text_question": "Текст", "kind": "text", "correct_answers": ["да"]},
        ],
    )
    alice = world["alice"]
    attempt = await begin(alice, world, test_id)
    items = by_text(attempt)

    bad_option = await alice.put(
        f"{PROGRESS}/{attempt['id']}/answers",
        json=[{"id": items["Несколько"]["id"], "student_answers": ["нет такого"]}],
    )
    assert bad_option.status_code == 400
    too_long = await alice.put(
        f"{PROGRESS}/{attempt['id']}/answers",
        json=[{"id": items["Текст"]["id"], "student_answer": "я" * 501}],
    )
    assert too_long.status_code == 400
    ok = await alice.put(
        f"{PROGRESS}/{attempt['id']}/answers",
        json=[
            {"id": items["Несколько"]["id"], "student_answers": ["x"]},
            {"id": items["Текст"]["id"], "student_answer": "да"},
        ],
    )
    assert ok.status_code == 200


async def test_question_payload_validation(world):
    teacher, test_id = world["teacher"], world["test_id"]
    url = f"{TESTS}/{test_id}/add_questions"
    bad = [
        {"text_question": "q", "kind": "text", "correct_answers": []},
        {"text_question": "q", "kind": "text"},
        {"text_question": "q", "kind": "multiple", "options": ["a", "b"], "correct_answers": ["a", "b"]},
        {"text_question": "q", "kind": "multiple", "options": ["a", "b", "c"], "correct_answers": ["a", "z"]},
        {"text_question": "q", "kind": "single", "options": ["a", "b"], "correct_answers": ["a", "b"]},
        {"text_question": "q", "kind": "weird", "options": ["a", "b"], "correct_answer": "a"},
        {"text_question": "q", "kind": "text", "correct_answers": ["1", "2", "3", "4", "5", "6"]},
    ]
    for question in bad:
        assert (await teacher.post(url, json=[question])).status_code == 422, question
    ok = await teacher.post(
        url, json=[{"text_question": "q", "kind": "multiple", "options": ["a", "b", "c"], "correct_answers": ["a", "c"]}]
    )
    assert ok.status_code == 200


async def test_edit_question_kind(world):
    teacher, test_id = world["teacher"], world["test_id"]
    first = (await teacher.get(f"{TESTS}/{test_id}")).json()["questions"][0]

    to_text = await teacher.patch(
        f"{TESTS}/{test_id}/questions/{first['id']}",
        json={"kind": "text", "correct_answers": ["Ответ"], "options": []},
    )
    assert to_text.status_code == 200
    assert to_text.json()["kind"] == "text" and to_text.json()["options"] == []
    assert to_text.json()["correct_answers"] == ["Ответ"] and to_text.json()["correct_answer"] == "Ответ"

    back = await teacher.patch(
        f"{TESTS}/{test_id}/questions/{first['id']}",
        json={"kind": "multiple", "options": ["a", "b", "c"], "correct_answers": ["a", "b"]},
    )
    assert back.status_code == 200 and back.json()["correct_answers"] == ["a", "b"]


async def test_analytics_counts_all_kinds(world):
    test_id = await make_test(
        world,
        [
            {"text_question": "Несколько", "kind": "multiple", "options": ["x", "y", "z"], "correct_answers": ["x", "z"]},
            {"text_question": "Текст", "kind": "text", "correct_answers": ["Москва"]},
        ],
    )
    alice, bob = world["alice"], world["bob"]
    await submit(alice, await begin(alice, world, test_id), {"Несколько": ["x", "z"], "Текст": "москва"})
    await submit(bob, await begin(bob, world, test_id), {"Несколько": ["x", "y"], "Текст": "Питер"})

    data = (
        await world["teacher"].get(f"/api/v1/course/{world['course_id']}/tests/{test_id}/analytics")
    ).json()
    stats = {item["text"]: item for item in data["questions"]}
    assert stats["Несколько"]["correct_percent"] == 50 and stats["Несколько"]["top_wrong"] == "x, y"
    assert stats["Текст"]["correct_percent"] == 50 and stats["Текст"]["top_wrong"] == "Питер"
