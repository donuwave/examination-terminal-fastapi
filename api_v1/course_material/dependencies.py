from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_user_id_in_access_token
from core.models import Course, CourseStudentAssociation, db_helper


async def get_course_for_member(
    course_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
) -> Course:
    """Курс доступен его преподавателю и записанным студентам."""
    course = await session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден")

    if course.teacher_id == user_id:
        return course

    enrolled = await session.scalar(
        select(CourseStudentAssociation.id).where(
            CourseStudentAssociation.course_id == course_id,
            CourseStudentAssociation.profile_id == user_id,
        )
    )
    if enrolled is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к курсу")
    return course


async def get_course_for_teacher(
    course: Course = Depends(get_course_for_member),
    user_id: int = Depends(get_user_id_in_access_token),
) -> Course:
    if course.teacher_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Материалы курса может менять только его преподаватель",
        )
    return course
