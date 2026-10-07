from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.decorators import role_required
from api_v1.auth.dependencies import get_user_id_in_access_token
from api_v1.test_progress import crud as test_progress_crud
from api_v1.test_progress.dependencies import (
    get_progress_test as get_progress_test_dependency,
)
from api_v1.test_progress.schemas import AnswerIn, TestProgressTest
from core.models import Course, TestProgress, db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["TestProgress"], dependencies=[Depends(http_bearer)])


@router.get("/", response_model=List[TestProgressTest])
async def get_list_progress_test(
    filter_date: Optional[int] = 0,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await test_progress_crud.get_list_test_progress(
        user_id=user_id,
        filter_date=filter_date or 0,
        session=session,
    )


@router.get("/course/{course_id}", response_model=TestProgressTest)
async def get_test_progress_test(
    course_id: int,
    test_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    progress = await get_progress_test_dependency(
        course_id=course_id, session=session, user_id=user_id, test_id=test_id
    )
    return test_progress_crud.to_view(progress)


@router.get("/{progress_test_id}", response_model=TestProgressTest)
async def get_progress_test(
    progress_test: TestProgress = Depends(get_progress_test_dependency),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Попытку видит её студент и преподаватель курса."""
    if progress_test.participant_id != user_id:
        course = await session.get(Course, progress_test.course_id)
        if course is None or course.teacher_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к попытке"
            )
    return test_progress_crud.to_view(progress_test)


@router.post("/{progress_test_id}/start-test", response_model=TestProgressTest)
@role_required("Студент")
async def start_test(
    request: Request,
    progress_test: TestProgress = Depends(get_progress_test_dependency),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    progress = await test_progress_crud.start_test(
        session=session, progress=progress_test, user_id=user_id
    )
    return test_progress_crud.to_view(progress)


@router.put("/{progress_test_id}/answers", response_model=TestProgressTest)
@role_required("Студент")
async def save_answers(
    request: Request,
    answers: List[AnswerIn],
    progress_test: TestProgress = Depends(get_progress_test_dependency),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Автосохранение ответов, пока тест идёт."""
    progress = await test_progress_crud.save_answers(
        session=session, progress=progress_test, user_id=user_id, answers=answers
    )
    return test_progress_crud.to_view(progress)


@router.post("/{progress_test_id}/completion-test", response_model=TestProgressTest)
@role_required("Студент")
async def completion_test(
    request: Request,
    answers: List[AnswerIn],
    progress_test: TestProgress = Depends(get_progress_test_dependency),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Завершает тест. Оценку считает сервер по сохранённым правильным ответам."""
    progress = await test_progress_crud.completion_test(
        session=session, progress=progress_test, user_id=user_id, answers=answers
    )
    return test_progress_crud.to_view(progress)
