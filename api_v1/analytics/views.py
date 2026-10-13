from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.analytics import crud
from api_v1.analytics.schemas import CourseAnalytics, TestAnalytics
from api_v1.course_material.dependencies import get_course_for_teacher
from core.models import Course, db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["Analytics"], dependencies=[Depends(http_bearer)])


@router.get("/{course_id}/analytics", response_model=CourseAnalytics)
async def get_course_analytics(
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Прогресс студентов, разделов и тестов курса. Только для преподавателя курса."""
    return await crud.course_analytics(session=session, course=course)


@router.get("/{course_id}/tests/{test_id}/analytics", response_model=TestAnalytics)
async def get_test_analytics(
    test_id: int,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Какие вопросы теста вызывают трудности и как распределены результаты."""
    return await crud.test_analytics(session=session, course=course, test_id=test_id)
