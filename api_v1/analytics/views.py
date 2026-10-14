from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.analytics import crud
from api_v1.analytics.export import csv_response, when
from api_v1.analytics.schemas import CourseAnalytics, TestAnalytics
from api_v1.course_material.dependencies import get_course_for_teacher
from api_v1.notification.service import person_name
from api_v1.test_progress import crud as progress_crud
from core.models import Test
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


STATUS_NAMES = {
    "finished": "Прошёл курс",
    "active": "Занимается",
    "stalled": "Давно без попыток",
    "new": "Не начал",
}
TEST_STATUS_NAMES = {
    "new": "Не начат",
    "in_progress": "Идёт",
    "passed": "Сдан",
    "retry": "Можно пересдать",
    "cooldown": "Пауза перед пересдачей",
    "waiting": "Ждёт решения",
}


@router.get("/{course_id}/analytics/export")
async def export_course_analytics(
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Таблица студентов курса в CSV."""
    data = await crud.course_analytics(session=session, course=course)
    rows = [
        (
            person_name(row.student),
            row.student.email,
            row.sections_passed,
            row.sections_total,
            "" if row.avg_best_percent is None else row.avg_best_percent,
            row.materials_viewed,
            row.materials_total,
            when(row.last_activity_at),
            STATUS_NAMES[row.status],
        )
        for row in data.students
    ]
    return csv_response(
        f"{course.name} - студенты.csv",
        [
            "Студент",
            "Почта",
            "Разделов сдано",
            "Разделов всего",
            "Средний результат, %",
            "Материалов открыто",
            "Материалов всего",
            "Последняя активность",
            "Статус",
        ],
        rows,
    )


@router.get("/{course_id}/tests/{test_id}/export")
async def export_test_results(
    test_id: int,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Результаты студентов по тесту в CSV."""
    results = await progress_crud.get_test_results(
        session=session, course_id=course.id, test_id=test_id
    )
    test = await session.get(Test, test_id)
    rows = [
        (
            person_name(row.student),
            row.student.email,
            TEST_STATUS_NAMES[row.status],
            row.attempts_used,
            row.attempts_allowed,
            "" if row.best_percent is None else row.best_percent,
            when(row.last_finished_at),
        )
        for row in results
    ]
    return csv_response(
        f"{test.name} - результаты.csv",
        ["Студент", "Почта", "Статус", "Попыток", "Попыток всего", "Лучший результат, %", "Последняя попытка"],
        rows,
    )
