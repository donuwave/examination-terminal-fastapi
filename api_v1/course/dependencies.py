from typing import Annotated

from fastapi import Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.models import (
    Course,
    CourseStudentAssociation,
    db_helper,
    CourseTestAssociation,
)


async def get_course_by_id(
    course_id: Annotated[int, Path],
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    course = await session.scalar(
        select(Course)
        .where(Course.id == course_id)
        .options(selectinload(Course.tests).joinedload(CourseTestAssociation.test))
        .options(
            selectinload(Course.students).joinedload(CourseStudentAssociation.student)
        )
    )

    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден")

    # Раньше здесь считалось, открыт ли доступ к тесту. Теперь доступ определяется прогрессом
    # студента, а поле осталось ради совместимости ответа.
    for association in course.tests:
        association.test.access_test = True

    return course
