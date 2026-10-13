from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.decorators import role_required
from api_v1.auth.dependencies import get_user_id_in_access_token
from api_v1.course import crud as course_crud
from api_v1.course.dependencies import get_course_by_id
from api_v1.course_material.dependencies import (
    get_course_for_member,
    get_course_for_teacher,
)
from api_v1.course.schemas import (
    CatalogCourse,
    CategoryGet,
    CourseGet,
    CourseItemGet,
    CourseUpdatePartial,
    LearningItem,
)
from core.models import db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["Course"], dependencies=[Depends(http_bearer)])


@router.get("/", response_model=list[CourseGet])
async def get_course(
    search: Optional[str] = Query(None, min_length=1, description="Поисковая строка"),
    sort_by: Optional[str] = Query(None),
    direction: Optional[int] = Query(None),
    category_id: Optional[int] = Query(None, description="Фильтр по типу курса"),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.get_list_course(
        session=session,
        user_id=user_id,
        search=search,
        direct=direction,
        sort_by=sort_by,
        category_id=category_id,
    )


@router.get("/learning", response_model=list[LearningItem])
async def get_learning(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Курсы студента: прогресс по разделам и следующий шаг."""
    return await course_crud.get_learning(session=session, user_id=user_id)


@router.get("/categories", response_model=list[CategoryGet])
async def get_categories(
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.get_categories(session=session)


@router.get("/catalog", response_model=list[CatalogCourse])
async def get_catalog(
    search: Optional[str] = Query(None, min_length=1, description="Поисковая строка"),
    category_id: Optional[int] = Query(None, description="Фильтр по типу курса"),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.get_catalog(
        session=session, user_id=user_id, search=search, category_id=category_id
    )


@router.post("/")
@role_required("Преподаватель")
async def create_course(
    request: Request,
    user_id: int = Depends(get_user_id_in_access_token),
    name: str = Form(),
    description: str = Form(),
    category_id: Optional[int] = Form(None),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.create_course(
        session=session,
        user_id=user_id,
        name=name,
        description=description,
        category_id=category_id,
    )


@router.get(
    "/{course_id}",
    response_model=CourseItemGet,
    dependencies=[Depends(get_course_for_member)],
)
async def get_item_course(
    course: CourseGet = Depends(get_course_by_id),
):
    return course


@router.patch("/{course_id}",
    dependencies=[Depends(get_course_for_teacher)],
)
@role_required("Преподаватель")
async def update_course(
    request: Request,
    course_update: CourseUpdatePartial,
    course: CourseGet = Depends(get_course_by_id),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.update_course(
        course=course, session=session, course_update=course_update
    )


@router.delete("/{course_id}",
    dependencies=[Depends(get_course_for_teacher)],
)
@role_required("Преподаватель")
async def delete_course(
    request: Request,
    course: CourseGet = Depends(get_course_by_id),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.delete_course(course=course, session=session)


@router.post("/{course_id}/add_student",
    dependencies=[Depends(get_course_for_teacher)],
)
@role_required("Преподаватель")
async def add_student_in_course(
    request: Request,
    student_ids: List[int],
    course: CourseGet = Depends(get_course_by_id),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.add_student_in_course(
        course=course, session=session, student_ids=student_ids
    )


@router.post("/{course_id}/delete_student",
    dependencies=[Depends(get_course_for_teacher)],
)
@role_required("Преподаватель")
async def delete_student_in_course(
    request: Request,
    student_id: int,
    course: CourseGet = Depends(get_course_by_id),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.delete_student_in_course(
        student_id=student_id, session=session, course=course
    )


@router.post("/{course_id}/leave")
@role_required("Студент")
async def leave_course(
    request: Request,
    user_id: int = Depends(get_user_id_in_access_token),
    course: CourseGet = Depends(get_course_by_id),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.delete_student_in_course(
        student_id=user_id, session=session, course=course
    )


@router.post("/{course_id}/enroll")
@role_required("Студент")
async def enroll_in_course(
    request: Request,
    course_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await course_crud.enroll_student(
        session=session, course_id=course_id, user_id=user_id
    )
