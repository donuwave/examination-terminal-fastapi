"""Профиль другого пользователя и его курсы по правилам доступа.

Кто что видит:
- свой профиль: всё;
- преподаватель: профиль студента своего курса с почтой и прогрессом только по своим курсам;
- любой пользователь: профиль преподавателя без почты и его курсы (витрина каталога);
- студент: профиль студента, с которым они на одном курсе, без почты и прогресса.
Всё остальное — 404, чтобы не раскрывать, что такой пользователь существует.
"""

from typing import Union

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api_v1.course_section.state import course_progress
from api_v1.profile.public_schemas import (
    ProfileCourse,
    ProfileCourses,
    PrivateProfile,
    PublicProfile,
)
from core.models import (
    Course,
    CourseStudentAssociation,
    CourseTestAssociation,
    MaterialView,
    Profile,
    TestProgress,
)
from core.models.test_progress import TestProgressResult

TEACHER, STUDENT = "Преподаватель", "Студент"


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Профиль не найден")


async def _load(session: AsyncSession, profile_id: int) -> Profile | None:
    return await session.get(Profile, profile_id)


async def _teaches(session: AsyncSession, teacher_id: int, student_id: int) -> bool:
    return (
        await session.scalar(
            select(Course.id)
            .join(CourseStudentAssociation, CourseStudentAssociation.course_id == Course.id)
            .where(Course.teacher_id == teacher_id, CourseStudentAssociation.profile_id == student_id)
            .limit(1)
        )
    ) is not None


async def _common_courses(session: AsyncSession, first: int, second: int) -> list[int]:
    other = aliased(CourseStudentAssociation)
    return list(
        await session.scalars(
            select(CourseStudentAssociation.course_id)
            .join(other, other.course_id == CourseStudentAssociation.course_id)
            .where(CourseStudentAssociation.profile_id == first, other.profile_id == second)
        )
    )


async def _access(session: AsyncSession, viewer: Profile, target: Profile) -> str:
    """Уровень доступа: self, owner (преподаватель студента), public, peer или none."""
    if viewer.id == target.id:
        return "self"
    if target.role.name == TEACHER:
        return "public"
    if viewer.role.name == TEACHER and await _teaches(session, viewer.id, target.id):
        return "owner"
    if viewer.role.name == STUDENT and await _common_courses(session, viewer.id, target.id):
        return "peer"
    return "none"


async def get_profile_card(
    session: AsyncSession, viewer_id: int, target_id: int
) -> Union[PrivateProfile, PublicProfile]:
    viewer = await _load(session, viewer_id)
    target = await _load(session, target_id)
    if viewer is None or target is None:
        raise _not_found()

    level = await _access(session, viewer, target)
    if level == "none":
        raise _not_found()

    base = dict(
        id=target.id, first_name=target.first_name, last_name=target.last_name, role=target.role.name
    )
    if level in ("self", "owner"):
        return PrivateProfile(**base, email=target.email)
    return PublicProfile(**base)


async def _best_percent(session: AsyncSession, course_id: int, student_id: int) -> int | None:
    """Средний по тестам курса лучший результат студента."""
    questions = (
        select(
            TestProgressResult.test_progress_id.label("attempt_id"),
            func.count(TestProgressResult.id).label("total"),
        )
        .group_by(TestProgressResult.test_progress_id)
        .subquery()
    )
    rows = (
        await session.execute(
            select(TestProgress.test_id, TestProgress.count_current_answer, questions.c.total)
            .join(questions, questions.c.attempt_id == TestProgress.id)
            .where(
                TestProgress.course_id == course_id,
                TestProgress.participant_id == student_id,
                TestProgress.status == 3,
            )
        )
    ).all()
    best: dict[int, int] = {}
    for test_id, correct, total in rows:
        if total:
            best[test_id] = max(best.get(test_id, 0), round((correct or 0) * 100 / total))
    return round(sum(best.values()) / len(best)) if best else None


async def _last_activity(session: AsyncSession, course_id: int, student_id: int) -> int | None:
    """Последняя попытка или просмотр материала студента в курсе."""
    attempt = await session.scalar(
        select(func.max(TestProgress.finished_at)).where(
            TestProgress.course_id == course_id,
            TestProgress.participant_id == student_id,
            TestProgress.status == 3,
        )
    )
    view = await session.scalar(
        select(func.max(MaterialView.last_viewed_at)).where(
            MaterialView.course_id == course_id, MaterialView.student_id == student_id
        )
    )
    stamps = [attempt] if attempt else []
    if view:
        stamps.append(int(view.timestamp()))
    return max(stamps) if stamps else None


async def _counts(session: AsyncSession, course_id: int) -> tuple[int, int]:
    students = await session.scalar(
        select(func.count(CourseStudentAssociation.id)).where(
            CourseStudentAssociation.course_id == course_id
        )
    )
    tests = await session.scalar(
        select(func.count(CourseTestAssociation.id)).where(
            CourseTestAssociation.course_id == course_id
        )
    )
    return students or 0, tests or 0


async def get_profile_courses(
    session: AsyncSession, viewer_id: int, target_id: int, limit: int, offset: int
) -> ProfileCourses:
    viewer = await _load(session, viewer_id)
    target = await _load(session, target_id)
    if viewer is None or target is None:
        raise _not_found()
    level = await _access(session, viewer, target)
    if level == "none":
        raise _not_found()

    if target.role.name == TEACHER:
        query = select(Course).where(Course.teacher_id == target.id)
        with_progress = False
    else:
        query = select(Course).join(
            CourseStudentAssociation, CourseStudentAssociation.course_id == Course.id
        ).where(CourseStudentAssociation.profile_id == target.id)
        if level == "owner":
            # Преподаватель видит курсы студента только свои.
            query = query.where(Course.teacher_id == viewer.id)
        elif level == "peer":
            query = query.where(Course.id.in_(await _common_courses(session, viewer.id, target.id)))
        with_progress = level in ("self", "owner")

    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    courses = (
        await session.scalars(query.order_by(Course.name).limit(limit).offset(offset))
    ).all()

    viewer_courses = set(
        await session.scalars(
            select(CourseStudentAssociation.course_id).where(
                CourseStudentAssociation.profile_id == viewer.id
            )
        )
    )

    items = []
    for course in courses:
        students_count, tests_count = await _counts(session, course.id)
        item = ProfileCourse(
            id=course.id,
            name=course.name,
            category=course.category,
            enrollment=course.enrollment,
            students_count=students_count,
            tests_count=tests_count,
            is_member=course.teacher_id == viewer.id or course.id in viewer_courses,
        )
        if with_progress:
            progress = await course_progress(session, course.id, target.id)
            item.sections_passed = progress.passed_count
            item.sections_total = len(progress.sections)
            item.avg_best_percent = await _best_percent(session, course.id, target.id)
            item.last_activity_at = await _last_activity(session, course.id, target.id)
        items.append(item)
    return ProfileCourses(courses=items, total=total)
