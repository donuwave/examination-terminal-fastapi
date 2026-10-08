from typing import List

from fastapi import APIRouter, Depends, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_user_id_in_access_token
from api_v1.course_material.dependencies import get_course_for_member, get_course_for_teacher
from api_v1.course_section import crud
from api_v1.course_section.schemas import SectionGet, SectionTitle
from core.models import Course, db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["CourseSection"], dependencies=[Depends(http_bearer)])


@router.get("/{course_id}/sections", response_model=List[SectionGet])
async def get_sections(
    course: Course = Depends(get_course_for_member),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await crud.list_sections(
        session=session,
        course_id=course.id,
        viewer_id=user_id,
        is_teacher=course.teacher_id == user_id,
    )


@router.post("/{course_id}/sections", status_code=status.HTTP_201_CREATED)
async def create_section(
    data: SectionTitle,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    section = await crud.create_section(session=session, course_id=course.id, title=data.title)
    return {"id": section.id}


@router.put("/{course_id}/sections/order", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_sections(
    ids: List[int],
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    await crud.reorder_sections(session=session, course_id=course.id, ids=ids)


@router.patch("/{course_id}/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def rename_section(
    section_id: int,
    data: SectionTitle,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    section = await crud.get_section(session, course.id, section_id)
    await crud.rename_section(session=session, section=section, title=data.title)


@router.delete("/{course_id}/sections/{section_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_section(
    section_id: int,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    section = await crud.get_section(session, course.id, section_id)
    await crud.delete_section(session=session, section=section)


@router.post("/{course_id}/sections/{section_id}/tests", status_code=status.HTTP_204_NO_CONTENT)
async def add_section_tests(
    section_id: int,
    test_ids: List[int],
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    section = await crud.get_section(session, course.id, section_id)
    await crud.add_tests(session=session, section=section, test_ids=test_ids)


@router.delete(
    "/{course_id}/sections/{section_id}/tests/{test_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_section_test(
    section_id: int,
    test_id: int,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    section = await crud.get_section(session, course.id, section_id)
    await crud.remove_test(session=session, section=section, test_id=test_id)
