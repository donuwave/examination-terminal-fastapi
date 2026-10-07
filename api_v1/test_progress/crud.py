import time
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.test_progress.schemas import AnswerIn, TestProgressTest
from core.models import TestProgress

READY, STARTED, FINISHED, OVERDUE = 1, 2, 3, 4


def seconds_left(progress: TestProgress) -> int | None:
    """Секунды до конца попытки: меньше из лимита времени и дедлайна."""
    if progress.status != STARTED or progress.attempt_date is None:
        return None
    end = min(progress.attempt_date + progress.timelimit, progress.deadline_date)
    return max(0, end - int(time.time()))


def grade(progress: TestProgress) -> None:
    progress.count_current_answer = sum(
        1
        for item in progress.result_test
        if item.student_answer is not None
        and item.student_answer == item.correct_answer
    )


async def finalize(session: AsyncSession, progress: TestProgress) -> None:
    progress.status = FINISHED
    grade(progress)
    await session.commit()


async def sync_state(session: AsyncSession, progress: TestProgress) -> TestProgress:
    """Переводит попытку в нужный статус, если срок вышел.

    Не начатый тест после дедлайна становится просроченным, а начатый,
    у которого кончилось время, засчитывается по сохранённым ответам.
    """
    if progress.status == READY and progress.deadline_date <= int(time.time()):
        progress.status = OVERDUE
        await session.commit()
    elif progress.status == STARTED and seconds_left(progress) == 0:
        await finalize(session, progress)
    return progress


def to_view(progress: TestProgress) -> TestProgressTest:
    """Ответ API: пока тест идёт, правильные ответы скрыты."""
    view = TestProgressTest.model_validate(progress, from_attributes=True)
    view.remaining_time = seconds_left(progress)
    if progress.status in (READY, STARTED):
        for item in view.result_test:
            item.correct_answer = None
    return view


async def get_list_test_progress_in_course(
    test_id: int, course_id: int, session: AsyncSession
):
    state = (
        select(TestProgress)
        .where(TestProgress.test_id == test_id)
        .where(TestProgress.course_id == course_id)
        .options(selectinload(TestProgress.result_test))
    )

    result: Result = await session.execute(state)
    items = [await sync_state(session, item) for item in result.scalars().all()]
    return [to_view(item) for item in items]


async def get_list_test_progress(user_id: int, filter_date: int, session: AsyncSession):
    state = (
        select(TestProgress)
        .where(TestProgress.participant_id == user_id)
        .where(TestProgress.deadline_date >= filter_date)
        .options(selectinload(TestProgress.result_test))
    )

    result: Result = await session.execute(state)
    items = [await sync_state(session, item) for item in result.scalars().all()]
    return [to_view(item) for item in items]


def _own(progress: TestProgress, user_id: int) -> None:
    if progress.participant_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Это не ваша попытка",
        )


def _apply_answers(progress: TestProgress, answers: List[AnswerIn]) -> None:
    by_id = {item.id: item for item in progress.result_test}
    for answer in answers:
        item = by_id.get(answer.id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Вопрос не относится к этой попытке",
            )
        if answer.student_answer is not None and answer.student_answer not in item.options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Такого варианта ответа нет",
            )
        item.student_answer = answer.student_answer


async def start_test(session: AsyncSession, progress: TestProgress, user_id: int):
    _own(progress, user_id)
    await sync_state(session, progress)

    if progress.status == STARTED:
        return progress
    if progress.status != READY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тест уже недоступен",
        )

    progress.status = STARTED
    progress.attempt_date = int(time.time())
    await session.commit()
    return progress


async def save_answers(
    session: AsyncSession,
    progress: TestProgress,
    user_id: int,
    answers: List[AnswerIn],
):
    _own(progress, user_id)
    await sync_state(session, progress)

    if progress.status != STARTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тест не идёт: ответы сохранить нельзя",
        )

    _apply_answers(progress, answers)
    await session.commit()
    return progress


async def completion_test(
    session: AsyncSession,
    progress: TestProgress,
    user_id: int,
    answers: List[AnswerIn],
):
    _own(progress, user_id)
    await sync_state(session, progress)

    if progress.status == FINISHED:
        return progress
    if progress.status != STARTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Тест не идёт: завершить его нельзя",
        )

    _apply_answers(progress, answers)
    await finalize(session, progress)
    return progress
