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
    TestProgress,
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

    # Доступ к тесту открыт, если по нему уже есть попытки студентов.
    opened = set(
        await session.scalars(
            select(TestProgress.test_id)
            .where(TestProgress.course_id == course_id)
            .distinct()
        )
    )
    for association in course.tests:
        association.test.access_test = association.test.id in opened

    return course
