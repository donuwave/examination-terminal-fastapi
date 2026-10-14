"""Лента активности студентов для преподавателя: попытки, чтение материалов, заявки и приглашения."""

from typing import List, Literal, Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.analytics.schemas import _StudentRef
from api_v1.test_progress.rules import FINISHED
from core.models import (
    Course,
    CourseMaterial,
    CourseRequest,
    MaterialView,
    Profile,
    Test,
    TestProgress,
)
from core.models.course_request import ACCEPTED, APPLICATION, INVITATION
from core.models.test_progress import TestProgressResult

EventKind = Literal["attempt", "material", "application", "invitation_accepted"]


class CourseRef(BaseModel):
    id: int
    name: str


class ActivityEvent(BaseModel):
    id: str
    kind: EventKind
    # Unix-секунды.
    at: int
    student: _StudentRef
    course: CourseRef
    # Название теста или материала.
    title: Optional[str] = None
    test_id: Optional[int] = None
    percent: Optional[int] = None
    passed: Optional[bool] = None


def _ref(profile: Profile) -> _StudentRef:
    return _StudentRef(
        id=profile.id,
        email=profile.email,
        first_name=profile.first_name,
        last_name=profile.last_name,
    )


async def students_feed(
    session: AsyncSession, teacher_id: int, limit: int, offset: int
) -> List[ActivityEvent]:
    """Свежие события по курсам преподавателя от новых к старым.

    Из каждого источника берём столько, сколько нужно для запрошенной страницы, затем сливаем.
    """
    take = limit + offset
    events: List[ActivityEvent] = []

    attempts = await session.execute(
        select(TestProgress, Course, Profile, Test)
        .join(Course, Course.id == TestProgress.course_id)
        .join(Profile, Profile.id == TestProgress.participant_id)
        .join(Test, Test.id == TestProgress.test_id)
        .where(
            Course.teacher_id == teacher_id,
            TestProgress.status == FINISHED,
            TestProgress.finished_at.is_not(None),
        )
        .options(selectinload(TestProgress.result_test))
        .order_by(TestProgress.finished_at.desc())
        .limit(take)
    )
    for attempt, course, student, test in attempts.all():
        total = len(attempt.result_test)
        events.append(
            ActivityEvent(
                id=f"attempt-{attempt.id}",
                kind="attempt",
                at=attempt.finished_at,
                student=_ref(student),
                course=CourseRef(id=course.id, name=course.name),
                title=test.name,
                test_id=test.id,
                percent=round((attempt.count_current_answer or 0) * 100 / total) if total else 0,
                passed=bool(attempt.passed),
            )
        )

    views = await session.execute(
        select(MaterialView, Course, Profile, CourseMaterial)
        .join(Course, Course.id == MaterialView.course_id)
        .join(Profile, Profile.id == MaterialView.student_id)
        .join(CourseMaterial, CourseMaterial.id == MaterialView.material_id)
        .where(Course.teacher_id == teacher_id)
        .order_by(MaterialView.last_viewed_at.desc())
        .limit(take)
    )
    for view, course, student, material in views.all():
        events.append(
            ActivityEvent(
                id=f"material-{view.id}",
                kind="material",
                at=int(view.last_viewed_at.timestamp()),
                student=_ref(student),
                course=CourseRef(id=course.id, name=course.name),
                title=material.title,
            )
        )

    requests = await session.execute(
        select(CourseRequest, Course, Profile)
        .join(Course, Course.id == CourseRequest.course_id)
        .join(Profile, Profile.id == CourseRequest.student_id)
        .where(Course.teacher_id == teacher_id)
        .order_by(CourseRequest.id.desc())
        .limit(take)
    )
    for request, course, student in requests.all():
        if request.kind == APPLICATION:
            kind, stamp = "application", request.created_at
        elif request.kind == INVITATION and request.status == ACCEPTED and request.decided_at:
            kind, stamp = "invitation_accepted", request.decided_at
        else:
            continue
        events.append(
            ActivityEvent(
                id=f"request-{request.id}",
                kind=kind,
                at=int(stamp.timestamp()),
                student=_ref(student),
                course=CourseRef(id=course.id, name=course.name),
            )
        )

    events.sort(key=lambda event: event.at, reverse=True)
    return events[offset : offset + limit]
