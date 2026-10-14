import time
from collections import Counter, defaultdict
from typing import Dict, List, Tuple

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.analytics.schemas import (
    Bucket,
    CourseAnalytics,
    QuestionStat,
    SectionStat,
    StudentStat,
    TestAnalytics,
    TestStat,
)
from api_v1.course_section.state import course_progress
from api_v1.test_progress.grading import given_answer
from api_v1.test_progress.rules import FINISHED, close_expired, is_item_correct
from api_v1.test_progress.schemas import StudentBrief
from core.models import (
    Course,
    CourseSection,
    CourseStudentAssociation,
    CourseMaterial,
    CourseTestAssociation,
    MaterialView,
    Profile,
    Test,
    TestExtraAttempt,
    TestProgress,
)
from core.models.test_progress import TestProgressResult

STALLED_AFTER_DAYS = 7


def _percent(correct: int | None, total: int) -> int:
    return round((correct or 0) * 100 / total) if total else 0


async def _finished_attempts(session: AsyncSession, course_id: int, test_id: int | None = None):
    """Завершённые попытки курса с числом вопросов в каждой."""
    questions = (
        select(
            TestProgressResult.test_progress_id.label("attempt_id"),
            func.count(TestProgressResult.id).label("total"),
        )
        .group_by(TestProgressResult.test_progress_id)
        .subquery()
    )
    query = (
        select(
            TestProgress.id,
            TestProgress.participant_id,
            TestProgress.test_id,
            TestProgress.count_current_answer,
            TestProgress.passed,
            TestProgress.attempt_date,
            TestProgress.finished_at,
            TestProgress.timelimit,
            questions.c.total,
        )
        .join(questions, questions.c.attempt_id == TestProgress.id)
        .where(TestProgress.course_id == course_id, TestProgress.status == FINISHED)
    )
    if test_id is not None:
        query = query.where(TestProgress.test_id == test_id)
    return (await session.execute(query)).all()


async def course_analytics(session: AsyncSession, course: Course) -> CourseAnalytics:
    students = (
        await session.scalars(
            select(Profile)
            .join(CourseStudentAssociation, CourseStudentAssociation.profile_id == Profile.id)
            .where(CourseStudentAssociation.course_id == course.id)
        )
    ).all()
    sections = (
        await session.scalars(
            select(CourseSection)
            .where(CourseSection.course_id == course.id)
            .order_by(CourseSection.position, CourseSection.id)
        )
    ).all()
    associations = (
        await session.scalars(
            select(CourseTestAssociation).where(
                CourseTestAssociation.course_id == course.id,
                CourseTestAssociation.section_id.is_not(None),
            )
        )
    ).all()
    tests = {
        test.id: test
        for test in (
            await session.scalars(select(Test).where(Test.id.in_([a.test_id for a in associations])))
        ).all()
    }
    section_title = {section.id: section.title for section in sections}

    # Просроченные попытки закрываем до подсчёта, иначе они бы остались «идущими».
    for student in students:
        await close_expired(session, student.id)

    # Лучший результат и число попыток по каждой паре «студент и тест», последняя активность.
    best: Dict[Tuple[int, int], int] = {}
    attempts_count: Dict[Tuple[int, int], int] = defaultdict(int)
    last_activity: Dict[int, int] = {}
    for row in await _finished_attempts(session, course.id):
        key = (row.participant_id, row.test_id)
        best[key] = max(best.get(key, 0), _percent(row.count_current_answer, row.total))
        attempts_count[key] += 1
        if row.finished_at:
            last_activity[row.participant_id] = max(
                last_activity.get(row.participant_id, 0), row.finished_at
            )

    # Просмотры материалов: сколько открыл каждый студент и когда в последний раз.
    materials_total = (
        await session.scalar(
            select(func.count(CourseMaterial.id)).where(CourseMaterial.course_id == course.id)
        )
    ) or 0
    viewed: Dict[int, int] = defaultdict(int)
    for student_id, count, last in (
        await session.execute(
            select(
                MaterialView.student_id,
                func.count(MaterialView.id),
                func.max(MaterialView.last_viewed_at),
            )
            .where(MaterialView.course_id == course.id)
            .group_by(MaterialView.student_id)
        )
    ).all():
        viewed[student_id] = count
        stamp = int(last.timestamp())
        last_activity[student_id] = max(last_activity.get(student_id, 0), stamp)

    now = int(time.time())
    section_reached: Dict[int, int] = defaultdict(int)
    section_passed: Dict[int, int] = defaultdict(int)
    test_passed: Dict[int, int] = defaultdict(int)
    test_waiting: Dict[int, int] = defaultdict(int)
    test_attempted: Dict[int, int] = defaultdict(int)
    passed_attempts: Dict[int, List[int]] = defaultdict(list)
    rows: List[StudentStat] = []

    for student in students:
        progress = await course_progress(session, course.id, student.id)
        for item in progress.sections:
            if item.status != "locked":
                section_reached[item.section.id] += 1
            if item.status == "passed":
                section_passed[item.section.id] += 1
        for test_id, state in progress.test_states.items():
            if state.attempts_used:
                test_attempted[test_id] += 1
            if state.status == "passed":
                test_passed[test_id] += 1
                passed_attempts[test_id].append(state.attempts_used)
            if state.status == "waiting":
                test_waiting[test_id] += 1

        percents = [value for (sid, _), value in best.items() if sid == student.id]
        total_sections = len(progress.sections)
        last = last_activity.get(student.id)
        if total_sections and progress.passed_count == total_sections:
            state_name = "finished"
        elif last is None:
            state_name = "new"
        elif now - last > STALLED_AFTER_DAYS * 86400:
            state_name = "stalled"
        else:
            state_name = "active"

        rows.append(
            StudentStat(
                student=StudentBrief.model_validate(student),
                sections_passed=progress.passed_count,
                sections_total=total_sections,
                avg_best_percent=round(sum(percents) / len(percents)) if percents else None,
                materials_viewed=viewed[student.id],
                materials_total=materials_total,
                last_activity_at=last,
                status=state_name,
            )
        )

    # Сначала те, кому нужно внимание: давно не было попыток, затем остальные по свежести.
    order = {"stalled": 0, "active": 1, "new": 2, "finished": 3}
    rows.sort(key=lambda row: (order[row.status], -(row.last_activity_at or 0)))

    test_rows: List[TestStat] = []
    for assoc in associations:
        test = tests[assoc.test_id]
        percents = [value for (_, tid), value in best.items() if tid == test.id]
        passed_list = passed_attempts.get(test.id, [])
        test_rows.append(
            TestStat(
                test_id=test.id,
                name=test.name,
                section_title=section_title.get(assoc.section_id),
                students_total=len(students),
                passed=test_passed[test.id],
                waiting=test_waiting[test.id],
                attempted=test_attempted[test.id],
                avg_best_percent=round(sum(percents) / len(percents)) if percents else None,
                avg_attempts_to_pass=(
                    round(sum(passed_list) / len(passed_list), 1) if passed_list else None
                ),
            )
        )
    position = {section.id: section.position for section in sections}
    section_of = {assoc.test_id: assoc.section_id for assoc in associations}
    test_rows.sort(key=lambda item: (position.get(section_of[item.test_id], 0), item.test_id))

    progress_values = [
        round(row.sections_passed * 100 / row.sections_total) for row in rows if row.sections_total
    ]
    return CourseAnalytics(
        students_total=len(students),
        finished_total=sum(1 for row in rows if row.status == "finished"),
        stalled_total=sum(1 for row in rows if row.status == "stalled"),
        avg_progress_percent=round(sum(progress_values) / len(progress_values)) if progress_values else 0,
        sections=[
            SectionStat(
                id=section.id,
                title=section.title,
                position=section.position,
                tests_count=sum(1 for a in associations if a.section_id == section.id),
                reached=section_reached[section.id],
                passed=section_passed[section.id],
            )
            for section in sections
        ],
        tests=test_rows,
        students=rows,
    )


BUCKETS = [(0, 19), (20, 39), (40, 59), (60, 79), (80, 100)]


async def test_analytics(session: AsyncSession, course: Course, test_id: int) -> TestAnalytics:
    in_course = await session.scalar(
        select(CourseTestAssociation.id).where(
            CourseTestAssociation.course_id == course.id, CourseTestAssociation.test_id == test_id
        )
    )
    test = await session.get(Test, test_id)
    if in_course is None or test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Теста нет в курсе")

    students = (
        await session.scalars(
            select(CourseStudentAssociation.profile_id).where(
                CourseStudentAssociation.course_id == course.id
            )
        )
    ).all()
    for student_id in students:
        await close_expired(session, student_id)

    attempts = await _finished_attempts(session, course.id, test_id)
    percents = [_percent(row.count_current_answer, row.total) for row in attempts]
    durations = [
        row.finished_at - row.attempt_date
        for row in attempts
        if row.finished_at and row.attempt_date and row.finished_at >= row.attempt_date
    ]
    timed_out = sum(
        1
        for row in attempts
        if row.finished_at and row.attempt_date and row.timelimit
        and row.finished_at - row.attempt_date >= row.timelimit
    )

    # Вопросы сравниваем по тексту: в попытке хранится копия вопроса на момент старта.
    answers = (
        await session.execute(
            select(TestProgressResult)
            .join(TestProgress, TestProgress.id == TestProgressResult.test_progress_id)
            .where(
                TestProgress.course_id == course.id,
                TestProgress.test_id == test_id,
                TestProgress.status == FINISHED,
            )
        )
    ).all()
    by_text: Dict[str, List[TestProgressResult]] = defaultdict(list)
    for (item,) in answers:
        by_text[item.text_question].append(item)

    questions: List[QuestionStat] = []
    for text, items in by_text.items():
        correct_count = sum(1 for item in items if is_item_correct(item))
        wrong = Counter(
            given
            for given in (
                given_answer(item.kind, item.student_answer, item.student_answers)
                for item in items
                if not is_item_correct(item)
            )
            if given
        )
        top = wrong.most_common(1)
        questions.append(
            QuestionStat(
                text=text,
                answered=len(items),
                correct=correct_count,
                correct_percent=round(correct_count * 100 / len(items)),
                top_wrong=top[0][0] if top else None,
                top_wrong_count=top[0][1] if top else 0,
            )
        )
    questions.sort(key=lambda item: (item.correct_percent, item.text))

    return TestAnalytics(
        test_id=test.id,
        name=test.name,
        attempts_total=len(attempts),
        students_attempted=len({row.participant_id for row in attempts}),
        pass_rate_percent=(
            round(sum(1 for row in attempts if row.passed) * 100 / len(attempts)) if attempts else None
        ),
        avg_percent=round(sum(percents) / len(percents)) if percents else None,
        avg_duration_seconds=round(sum(durations) / len(durations)) if durations else None,
        timed_out=timed_out,
        questions=questions,
        distribution=[
            Bucket(label=f"{low}–{high}%", count=sum(1 for value in percents if low <= value <= high))
            for low, high in BUCKETS
        ],
    )
