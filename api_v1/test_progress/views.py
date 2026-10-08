from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.decorators import role_required
from api_v1.auth.dependencies import get_user_id_in_access_token
from api_v1.course_material.dependencies import get_course_for_teacher
from api_v1.test_progress import crud
from api_v1.test_progress.dependencies import get_progress_test
from api_v1.test_progress.schemas import (
    AnswerIn,
    GrantIn,
    StartIn,
    TestProgressTest,
    TestResultRow,
)
from core.models import Course, TestProgress, db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["TestProgress"], dependencies=[Depends(http_bearer)])


@router.get("/", response_model=List[TestProgressTest])
async def get_my_attempts(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Все попытки текущего студента."""
    return await crud.list_attempts(session=session, user_id=user_id)


@router.post("/start", response_model=TestProgressTest)
@role_required("Студент")
async def start_attempt(
    request: Request,
    data: StartIn,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Начинает попытку или возвращает уже идущую."""
    attempt = await crud.start_attempt(
        session=session, user_id=user_id, course_id=data.course_id, test_id=data.test_id
    )
    return await crud.view_attempt(session, attempt)


@router.get(
    "/results",
    response_model=List[TestResultRow],
    dependencies=[Depends(get_course_for_teacher)],
)
async def get_test_results(
    course_id: int,
    test_id: int,
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Результаты теста по студентам курса. Только для преподавателя курса."""
    return await crud.get_test_results(session=session, course_id=course_id, test_id=test_id)


@router.post("/grant", status_code=status.HTTP_204_NO_CONTENT)
async def grant_extra_attempt(
    data: GrantIn,
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
    user_id: int = Depends(get_user_id_in_access_token),
):
    """Преподаватель курса выдаёт студенту ещё одну попытку."""
    course = await session.get(Course, data.course_id)
    if course is None or course.teacher_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к курсу")
    await crud.grant_extra_attempt(
        session=session,
        course_id=data.course_id,
        test_id=data.test_id,
        student_id=data.student_id,
    )


@router.get("/{progress_test_id}", response_model=TestProgressTest)
async def get_attempt(
    progress_test: TestProgress = Depends(get_progress_test),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Попытку видит её студент и преподаватель курса."""
    if progress_test.participant_id != user_id:
        course = await session.get(Course, progress_test.course_id)
        if course is None or course.teacher_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к попытке")
    return await crud.view_attempt(session, progress_test)


@router.put("/{progress_test_id}/answers", response_model=TestProgressTest)
@role_required("Студент")
async def save_answers(
    request: Request,
    answers: List[AnswerIn],
    progress_test: TestProgress = Depends(get_progress_test),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Автосохранение ответов, пока идёт попытка."""
    progress = await crud.save_answers(
        session=session, progress=progress_test, user_id=user_id, answers=answers
    )
    return await crud.view_attempt(session, progress)


@router.post("/{progress_test_id}/completion-test", response_model=TestProgressTest)
@role_required("Студент")
async def completion_test(
    request: Request,
    answers: List[AnswerIn],
    progress_test: TestProgress = Depends(get_progress_test),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Завершает попытку. Оценку и итог считает сервер."""
    progress = await crud.completion_test(
        session=session, progress=progress_test, user_id=user_id, answers=answers
    )
    return await crud.view_attempt(session, progress)
