from typing import List

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.decorators import role_required
from api_v1.auth.dependencies import get_user_id_in_access_token
from api_v1.course.dependencies import get_course_by_id
from api_v1.course.schemas import CourseGet
from api_v1.course_test import crud as test_crud
from api_v1.course_test.dependencies import get_own_test
from api_v1.course_test.schemas import TestGet, TestUpdate
from api_v1.questions import crud as question_crud
from api_v1.questions.schemas import QuestionBase, QuestionGet, QuestionUpdatePartial
from core.models import db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["Test"], dependencies=[Depends(http_bearer)])


@router.get("/", response_model=List[TestGet])
async def get_tests(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await test_crud.get_list_test(session=session, user_id=user_id)


@router.get("/{test_id}", response_model=TestGet)
async def get_test_detail(test=Depends(get_own_test)):
    """Тест с правильными ответами. Только для автора."""
    return test


@router.post("/")
@role_required("Преподаватель")
async def create_test(
    request: Request,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
    name_test: str = Form(),
    time_limit: int = Form(),
    pass_percent: int = Form(60, ge=1, le=100),
    max_attempts: int = Form(2, ge=1, le=10),
    retry_delay_minutes: int = Form(120, ge=0, le=10080),
):
    return await test_crud.create_test(
        session=session,
        user_id=user_id,
        name=name_test,
        time_limit=time_limit,
        pass_percent=pass_percent,
        max_attempts=max_attempts,
        retry_delay_minutes=retry_delay_minutes,
    )


@router.post("/{test_id}/add_questions")
@role_required("Преподаватель")
async def add_questions_in_test(
    request: Request,
    questions: List[QuestionBase],
    test=Depends(get_own_test),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await test_crud.add_questions_in_test(test=test, session=session, questions=questions)


@router.put("/{test_id}/questions/order", status_code=status.HTTP_204_NO_CONTENT)
@role_required("Преподаватель")
async def reorder_questions(
    request: Request,
    ids: List[int],
    test=Depends(get_own_test),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Порядок вопросов в редакторе."""
    await test_crud.reorder_questions(session=session, test=test, ids=ids)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{test_id}", response_model=TestGet)
@role_required("Преподаватель")
async def update_test(
    request: Request,
    data: TestUpdate,
    test=Depends(get_own_test),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await test_crud.update_test(session=session, test=test, data=data)


@router.delete("/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
@role_required("Преподаватель")
async def delete_test(
    request: Request,
    test=Depends(get_own_test),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    await test_crud.delete_test(session=session, test=test)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{test_id}/questions/{question_id}", response_model=QuestionGet)
@role_required("Преподаватель")
async def update_question(
    request: Request,
    question_id: int,
    data: QuestionUpdatePartial,
    test=Depends(get_own_test),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    question = test_crud.find_question(test, question_id)
    return await question_crud.update_question(
        question_update=data, session=session, question=question
    )


@router.delete("/{test_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
@role_required("Преподаватель")
async def delete_question(
    request: Request,
    question_id: int,
    test=Depends(get_own_test),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    await test_crud.delete_question(session=session, test=test, question_id=question_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
