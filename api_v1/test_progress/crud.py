import random
import time
from collections import defaultdict
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import distinct, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, noload, selectinload

from api_v1.course_section.state import course_progress
from api_v1.notification import service as notifications
from api_v1.test_progress.rules import (
    is_item_correct,
    FINISHED,
    STARTED,
    close_expired,
    compute_state,
    finalize,
    load_attempts,
    load_extras,
    reveal_answers,
    seconds_left,
    sync_state,
)
from api_v1.test_progress.schemas import (
    AnswerIn,
    AttemptStats,
    StudentBrief,
    TestProgressTest,
    TestResultRow,
    TestState,
)
from core.models import (
    Course,
    CourseStudentAssociation,
    CourseTestAssociation,
    Profile,
    Test,
    TestExtraAttempt,
    TestProgress,
    TestQuestionAssociation,
)
from core.models.test_progress import TestProgressResult


MAX_TEXT_ANSWER_LENGTH = 500


def to_view(
    progress: TestProgress, state: TestState | None = None, reveal: bool = False
) -> TestProgressTest:
    """Ответ API. Пока нельзя раскрывать ответы, правильные варианты скрыты."""
    view = TestProgressTest.model_validate(progress, from_attributes=True)
    view.remaining_time = seconds_left(progress)
    view.state = state
    finished = progress.status == FINISHED
    for source, item in zip(progress.result_test, view.result_test):
        if finished:
            item.is_correct = is_item_correct(source)
        if not (reveal and finished):
            item.correct_answer = None
            item.correct_answers = None
    return view


async def view_attempt(session: AsyncSession, progress: TestProgress) -> TestProgressTest:
    """Попытка вместе с состоянием студента по тесту, чтобы экран знал, что делать дальше."""
    attempts = await load_attempts(
        session, progress.course_id, progress.participant_id, progress.test_id
    )
    extras = await load_extras(session, progress.course_id, progress.participant_id)
    state = compute_state(
        progress.test, attempts.get(progress.test_id, []), extras.get(progress.test_id, 0)
    )
    return to_view(progress, state, reveal_answers(state))


async def list_attempts(
    session: AsyncSession,
    user_id: int,
    limit: int,
    offset: int = 0,
    finished_from: int | None = None,
    finished_to: int | None = None,
) -> List[TestProgressTest]:
    """Попытки студента от свежих к старым, страницей.

    Видимость правильных ответов зависит от всех попыток по тесту, поэтому состояние
    считаем по облегчённой выборке без ответов, а ответы подгружаем только для страницы.
    """
    await close_expired(session, user_id)

    everything = (
        await session.scalars(
            select(TestProgress)
            .where(TestProgress.participant_id == user_id)
            .options(noload(TestProgress.result_test))
        )
    ).all()
    grouped: dict[tuple[int, int], list[TestProgress]] = defaultdict(list)
    for attempt in everything:
        grouped[(attempt.course_id, attempt.test_id)].append(attempt)

    extras_rows = await session.execute(
        select(TestExtraAttempt.course_id, TestExtraAttempt.test_id, TestExtraAttempt.extra).where(
            TestExtraAttempt.student_id == user_id
        )
    )
    extras = {(course_id, test_id): extra for course_id, test_id, extra in extras_rows.all()}

    query = select(TestProgress).where(TestProgress.participant_id == user_id)
    if finished_from is not None:
        query = query.where(TestProgress.finished_at >= finished_from)
    if finished_to is not None:
        query = query.where(TestProgress.finished_at < finished_to)
    page = (
        await session.scalars(
            query.options(selectinload(TestProgress.result_test))
            .order_by(TestProgress.id.desc())
            .limit(limit)
            .offset(offset)
            # Подгруженные облегчённо попытки уже в сессии без ответов: перечитываем их.
            .execution_options(populate_existing=True)
        )
    ).all()

    result = []
    for attempt in page:
        key = (attempt.course_id, attempt.test_id)
        state = compute_state(attempt.test, grouped[key], extras.get(key, 0))
        result.append(to_view(attempt, None, reveal_answers(state)))
    return result


async def attempt_stats(session: AsyncSession, user_id: int) -> AttemptStats:
    await close_expired(session, user_id)
    finished = await session.scalar(
        select(func.count(TestProgress.id)).where(
            TestProgress.participant_id == user_id, TestProgress.status == FINISHED
        )
    )
    passed_tests = await session.scalar(
        select(func.count(distinct(tuple_(TestProgress.course_id, TestProgress.test_id)))).where(
            TestProgress.participant_id == user_id, TestProgress.passed.is_(True)
        )
    )
    return AttemptStats(finished=finished or 0, passed_tests=passed_tests or 0)


def _apply_answers(progress: TestProgress, answers: List[AnswerIn]) -> None:
    by_id = {item.id: item for item in progress.result_test}
    for answer in answers:
        item = by_id.get(answer.id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Вопрос не относится к этой попытке",
            )
        if item.kind == "multiple":
            chosen = answer.student_answers or []
            if any(option not in item.options for option in chosen) or len(set(chosen)) != len(chosen):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Такого варианта ответа нет",
                )
            item.student_answers = chosen or None
        elif item.kind == "text":
            text = (answer.student_answer or "").strip()
            if len(text) > MAX_TEXT_ANSWER_LENGTH:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ответ не длиннее {MAX_TEXT_ANSWER_LENGTH} символов",
                )
            item.student_answer = text or None
        else:
            if answer.student_answer is not None and answer.student_answer not in item.options:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Такого варианта ответа нет",
                )
            item.student_answer = answer.student_answer


def _own(progress: TestProgress, user_id: int) -> None:
    if progress.participant_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша попытка")


async def start_attempt(
    session: AsyncSession, user_id: int, course_id: int, test_id: int
) -> TestProgress:
    """Начинает попытку, если раздел открыт и правила прохождения это позволяют."""
    enrolled = await session.scalar(
        select(CourseStudentAssociation.id).where(
            CourseStudentAssociation.course_id == course_id,
            CourseStudentAssociation.profile_id == user_id,
        )
    )
    if enrolled is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не записаны на курс")

    assoc = await session.scalar(
        select(CourseTestAssociation)
        .where(CourseTestAssociation.course_id == course_id, CourseTestAssociation.test_id == test_id)
        .options(
            selectinload(CourseTestAssociation.test)
            .selectinload(Test.questions)
            .joinedload(TestQuestionAssociation.question)
        )
    )
    if assoc is None or assoc.section_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Теста нет в курсе")

    progress = await course_progress(session, course_id, user_id)
    if assoc.section_id not in progress.unlocked_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Раздел ещё закрыт: сдайте тесты предыдущих разделов",
        )

    state = progress.test_states[test_id]
    test = assoc.test

    if state.status == "in_progress":
        return await session.get(
            TestProgress, state.active_attempt_id, options=[selectinload(TestProgress.result_test)]
        )
    if state.status == "passed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Тест уже сдан")
    if state.status == "waiting":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Попытки закончились. Дальше решает преподаватель",
        )
    if state.status == "cooldown":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пересдать тест можно будет чуть позже",
        )
    if not test.questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="В тесте нет вопросов")

    questions = [assoc_q.question for assoc_q in test.questions]
    random.shuffle(questions)
    results = []
    for question in questions:
        options = list(question.options)
        random.shuffle(options)
        results.append(
            TestProgressResult(
                text_question=question.text_question,
                kind=question.kind,
                options=options,
                correct_answer=question.correct_answer,
                correct_answers=list(question.correct_answers) or [question.correct_answer],
                student_answer=None,
            )
        )

    attempt = TestProgress(
        test_id=test_id,
        course_id=course_id,
        participant_id=user_id,
        status=STARTED,
        attempt_no=state.attempts_used + 1,
        attempt_date=int(time.time()),
        timelimit=test.time_limit,
        result_test=results,
    )
    session.add(attempt)
    await session.commit()
    await session.refresh(attempt, attribute_names=["result_test"])
    return attempt


async def save_answers(
    session: AsyncSession, progress: TestProgress, user_id: int, answers: List[AnswerIn]
) -> TestProgress:
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
    session: AsyncSession, progress: TestProgress, user_id: int, answers: List[AnswerIn]
) -> TestProgress:
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


async def get_test_results(session: AsyncSession, course_id: int, test_id: int) -> List[TestResultRow]:
    """Результаты теста по всем студентам курса."""
    test = await session.get(Test, test_id)
    in_course = await session.scalar(
        select(CourseTestAssociation.id).where(
            CourseTestAssociation.course_id == course_id,
            CourseTestAssociation.test_id == test_id,
        )
    )
    if test is None or in_course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Теста нет в курсе")

    students = (
        await session.scalars(
            select(Profile)
            .join(CourseStudentAssociation, CourseStudentAssociation.profile_id == Profile.id)
            .where(CourseStudentAssociation.course_id == course_id)
        )
    ).all()

    attempts = (
        await session.scalars(
            select(TestProgress)
            .where(TestProgress.course_id == course_id, TestProgress.test_id == test_id)
            .options(selectinload(TestProgress.result_test))
            .order_by(TestProgress.attempt_no, TestProgress.id)
        )
    ).all()
    by_student: dict[int, list[TestProgress]] = defaultdict(list)
    for attempt in attempts:
        await sync_state(session, attempt)
        by_student[attempt.participant_id].append(attempt)

    extras_rows = await session.execute(
        select(TestExtraAttempt.student_id, TestExtraAttempt.extra).where(
            TestExtraAttempt.course_id == course_id, TestExtraAttempt.test_id == test_id
        )
    )
    extras = {student_id: extra for student_id, extra in extras_rows.all()}

    rows = []
    for student in students:
        mine = by_student.get(student.id, [])
        state = compute_state(test, mine, extras.get(student.id, 0))
        finished = [item for item in mine if item.status == FINISHED]
        rows.append(
            TestResultRow(
                student=StudentBrief.model_validate(student),
                status=state.status,
                attempts_used=state.attempts_used,
                attempts_allowed=state.attempts_allowed,
                best_percent=state.best_percent,
                last_attempt_id=state.last_attempt_id,
                last_finished_at=finished[-1].finished_at if finished else None,
            )
        )
    return rows


async def grant_extra_attempt(
    session: AsyncSession, course_id: int, test_id: int, student_id: int
) -> None:
    """Преподаватель выдаёт ещё одну попытку студенту, у которого они закончились."""
    enrolled = await session.scalar(
        select(CourseStudentAssociation.id).where(
            CourseStudentAssociation.course_id == course_id,
            CourseStudentAssociation.profile_id == student_id,
        )
    )
    test = await session.get(Test, test_id)
    if enrolled is None or test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Студент или тест не найдены")

    attempts = await load_attempts(session, course_id, student_id, test_id)
    extras = await load_extras(session, course_id, student_id)
    state = compute_state(test, attempts.get(test_id, []), extras.get(test_id, 0))
    if state.status != "waiting":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дополнительная попытка нужна только тем, у кого попытки закончились",
        )

    record = await session.scalar(
        select(TestExtraAttempt).where(
            TestExtraAttempt.course_id == course_id,
            TestExtraAttempt.test_id == test_id,
            TestExtraAttempt.student_id == student_id,
        )
    )
    if record is None:
        session.add(
            TestExtraAttempt(course_id=course_id, test_id=test_id, student_id=student_id, extra=1)
        )
    else:
        record.extra += 1
    course = await session.get(Course, course_id)
    await notifications.notify(
        session,
        student_id,
        notifications.EXTRA_ATTEMPT,
        "Дополнительная попытка",
        f"Преподаватель дал вам ещё одну попытку теста «{test.name}» в курсе «{course.name}»",
        f"/courses/{course_id}",
    )
    await session.commit()
