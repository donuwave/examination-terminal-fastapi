from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.decorators import role_required
from api_v1.auth.dependencies import get_user_id_in_access_token
from api_v1.course_material.dependencies import get_course_for_teacher
from api_v1.course_request import crud
from api_v1.course_request.schemas import InviteIn, RequestGet
from core.models import Course, db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["CourseRequest"], dependencies=[Depends(http_bearer)])


# --- Студент ---------------------------------------------------------------


@router.post("/{course_id}/apply", response_model=RequestGet, status_code=status.HTTP_201_CREATED)
@role_required("Студент")
async def apply(
    request: Request,
    course_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Заявка на курс, на который нельзя записаться сразу."""
    course = await session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден")
    return await crud.apply(session=session, course=course, student_id=user_id)


@router.delete("/{course_id}/apply", status_code=status.HTTP_204_NO_CONTENT)
@role_required("Студент")
async def cancel_application(
    request: Request,
    course_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    await crud.cancel_application(session=session, course_id=course_id, student_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Преподаватель ---------------------------------------------------------


@router.get("/{course_id}/requests", response_model=List[RequestGet])
async def list_requests(
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Заявки студентов и отправленные приглашения, которые ждут решения."""
    return await crud.list_for_course(session=session, course_id=course.id)


@router.post("/{course_id}/invite", response_model=RequestGet, status_code=status.HTTP_201_CREATED)
async def invite_student(
    data: InviteIn,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await crud.invite(session=session, course=course, email=data.email)


@router.post("/{course_id}/requests/{request_id}/approve", response_model=RequestGet)
async def approve_request(
    request_id: int,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await crud.decide_application(
        session=session, course_id=course.id, request_id=request_id, approve=True
    )


@router.post("/{course_id}/requests/{request_id}/reject", response_model=RequestGet)
async def reject_request(
    request_id: int,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await crud.decide_application(
        session=session, course_id=course.id, request_id=request_id, approve=False
    )


@router.delete("/{course_id}/requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(
    request_id: int,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Отзывает отправленное приглашение."""
    await crud.cancel_invitation(session=session, course_id=course.id, request_id=request_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Приглашения студента --------------------------------------------------

invitations_router = APIRouter(tags=["Invitations"], dependencies=[Depends(http_bearer)])


@invitations_router.get("/", response_model=List[RequestGet])
async def my_invitations(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await crud.invitations_of(session=session, student_id=user_id)


@invitations_router.post("/{request_id}/accept", response_model=RequestGet)
async def accept_invitation(
    request_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await crud.answer_invitation(
        session=session, request_id=request_id, student_id=user_id, accept=True
    )


@invitations_router.post("/{request_id}/decline", response_model=RequestGet)
async def decline_invitation(
    request_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await crud.answer_invitation(
        session=session, request_id=request_id, student_id=user_id, accept=False
    )
