"""Правила прохождения тестов: время попытки, итог, паузы и состояние студента."""

import time
from collections import defaultdict
from typing import Dict, Iterable, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.test_progress.schemas import TestState
from api_v1.notification import service as notifications
from core.models import Course, Profile, Test, TestExtraAttempt, TestProgress

STARTED, FINISHED = 2, 3


def seconds_left(progress: TestProgress) -> int | None:
    """Секунды до конца идущей попытки."""
    if progress.status != STARTED or progress.attempt_date is None:
        return None
    end = progress.attempt_date + progress.timelimit
    return max(0, end - int(time.time()))


def correct_count(progress: TestProgress) -> int:
    return sum(
        1
        for item in progress.result_test
        if item.student_answer is not None and item.student_answer == item.correct_answer
    )


def percent_of(progress: TestProgress) -> int:
    total = len(progress.result_test)
    return round(correct_count(progress) * 100 / total) if total else 0


async def finalize(
    session: AsyncSession, progress: TestProgress, finished_at: int | None = None
) -> None:
    """Завершает попытку и решает, сдан ли тест."""
    total = len(progress.result_test)
    correct = correct_count(progress)
    progress.status = FINISHED
    progress.finished_at = finished_at if finished_at is not None else int(time.time())
    progress.count_current_answer = correct
    progress.passed = bool(total) and correct * 100 >= progress.test.pass_percent * total
    await _tell_teacher_if_out(session, progress)
    await session.commit()


async def _tell_teacher_if_out(session: AsyncSession, progress: TestProgress) -> None:
    """Если после этой попытки у студента не осталось попыток, преподавателю нужно решить, что дальше."""
    if progress.passed:
        return
    attempts = await load_attempts(
        session, progress.course_id, progress.participant_id, progress.test_id
    )
    extras = await load_extras(session, progress.course_id, progress.participant_id)
    state = compute_state(
        progress.test, attempts.get(progress.test_id, []), extras.get(progress.test_id, 0)
    )
    if state.status != "waiting":
        return

    course = await session.get(Course, progress.course_id)
    student = await session.get(Profile, progress.participant_id)
    await notifications.notify(
        session,
        course.teacher_id,
        notifications.ATTEMPTS_OUT,
        "Нужно ваше решение",
        f"У студента {notifications.person_name(student)} закончились попытки теста "
        f"«{progress.test.name}» в курсе «{course.name}»",
        f"/courses/{course.id}/tests/{progress.test_id}/results",
    )


async def sync_state(session: AsyncSession, progress: TestProgress) -> TestProgress:
    """Если время идущей попытки вышло, засчитываем её по сохранённым ответам.

    Завершение датируем концом отведённого времени, а не моментом, когда студент вернулся:
    от него считается пауза до пересдачи и день в ленте активности.
    """
    if progress.status == STARTED and seconds_left(progress) == 0:
        await finalize(session, progress, finished_at=progress.attempt_date + progress.timelimit)
    return progress


async def close_expired(session: AsyncSession, student_id: int) -> None:
    """Закрывает все просроченные попытки студента: ни одна не остаётся «идущей» навсегда."""
    now = int(time.time())
    started = await session.scalars(
        select(TestProgress)
        .where(
            TestProgress.participant_id == student_id,
            TestProgress.status == STARTED,
            TestProgress.attempt_date + TestProgress.timelimit <= now,
        )
        .options(selectinload(TestProgress.result_test))
    )
    for attempt in started.all():
        await sync_state(session, attempt)


async def load_attempts(
    session: AsyncSession, course_id: int, student_id: int, test_id: int | None = None
) -> Dict[int, List[TestProgress]]:
    """Попытки студента по тестам курса, сгруппированные по тесту."""
    state = (
        select(TestProgress)
        .where(TestProgress.course_id == course_id, TestProgress.participant_id == student_id)
        .options(selectinload(TestProgress.result_test))
        .order_by(TestProgress.attempt_no, TestProgress.id)
    )
    if test_id is not None:
        state = state.where(TestProgress.test_id == test_id)

    grouped: Dict[int, List[TestProgress]] = defaultdict(list)
    for attempt in (await session.scalars(state)).all():
        await sync_state(session, attempt)
        grouped[attempt.test_id].append(attempt)
    return grouped


async def load_extras(session: AsyncSession, course_id: int, student_id: int) -> Dict[int, int]:
    rows = await session.execute(
        select(TestExtraAttempt.test_id, TestExtraAttempt.extra).where(
            TestExtraAttempt.course_id == course_id, TestExtraAttempt.student_id == student_id
        )
    )
    return {test_id: extra for test_id, extra in rows.all()}


def compute_state(test: Test, attempts: Iterable[TestProgress], extra: int) -> TestState:
    """Состояние студента по тесту по его попыткам и выданным дополнительным."""
    now = int(time.time())
    attempts = sorted(attempts, key=lambda item: (item.attempt_no, item.id))
    finished = [item for item in attempts if item.status == FINISHED]
    active = next((item for item in attempts if item.status == STARTED), None)
    allowed = test.max_attempts + extra
    best = max((percent_of(item) for item in finished), default=None)

    state = TestState(
        status="new",
        attempts_used=len(finished),
        attempts_allowed=allowed,
        best_percent=best,
        active_attempt_id=active.id if active else None,
        last_attempt_id=finished[-1].id if finished else None,
    )

    if any(item.passed for item in finished):
        state.status = "passed"
    elif active is not None:
        state.status = "in_progress"
    elif not finished:
        state.status = "new"
    elif len(finished) >= allowed:
        state.status = "waiting"
    else:
        last = finished[-1]
        # Пауза нужна только в пределах обычных попыток; выданные преподавателем идут без неё.
        ready_at = (last.finished_at or 0) + test.retry_delay_minutes * 60
        if last.attempt_no < test.max_attempts and now < ready_at:
            state.status = "cooldown"
            state.next_attempt_at = ready_at
        else:
            state.status = "retry"
    return state


def reveal_answers(state: TestState) -> bool:
    """Правильные ответы открываем, когда тест сдан или попытки закончились."""
    return state.status in ("passed", "waiting")
