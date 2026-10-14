from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_user_id_in_access_token
from api_v1.course_material.dependencies import get_course_for_member
from api_v1.course_section.state import course_progress
from api_v1.notification.service import person_name
from core.models import Course, CourseStudentAssociation, Profile, TestProgress, db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["Certificate"], dependencies=[Depends(http_bearer)])


class Certificate(BaseModel):
    student_name: str
    course_name: str
    teacher_name: str
    # Когда сдан последний тест курса, unix-секунды.
    finished_at: Optional[int] = None
    number: str


@router.get("/{course_id}/certificate", response_model=Certificate)
async def get_certificate(
    course: Course = Depends(get_course_for_member),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Сертификат о прохождении курса. Выдаётся студенту, который сдал все разделы."""
    enrolled = await session.scalar(
        select(CourseStudentAssociation.id).where(
            CourseStudentAssociation.course_id == course.id,
            CourseStudentAssociation.profile_id == user_id,
        )
    )
    if enrolled is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Сертификат выдают студентам курса")

    progress = await course_progress(session, course.id, user_id)
    if not progress.sections or progress.passed_count != len(progress.sections):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Курс ещё не пройден")

    finished_at = await session.scalar(
        select(func.max(TestProgress.finished_at)).where(
            TestProgress.course_id == course.id,
            TestProgress.participant_id == user_id,
            TestProgress.passed.is_(True),
        )
    )
    student = await session.get(Profile, user_id)
    teacher = await session.get(Profile, course.teacher_id)
    stamp = datetime.fromtimestamp(finished_at or 0, tz=timezone.utc).strftime("%Y%m%d")
    return Certificate(
        student_name=person_name(student),
        course_name=course.name,
        teacher_name=person_name(teacher),
        finished_at=finished_at,
        number=f"ET-{course.id}-{user_id}-{stamp}",
    )
