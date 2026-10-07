from typing import Union, Optional

from fastapi import HTTPException, status
from sqlalchemy import select, Result, or_, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.course.schemas import CatalogCourse, CourseGet, CourseUpdatePartial
from api_v1.profile.schemas import ProfileGet
from api_v1.course_test.dependencies import get_test
from api_v1.profile import crud as crud_profile
from api_v1.profile.crud import get_profile
from api_v1.course_material.storage import delete_files
from core.models import (
    Course,
    CourseCategory,
    CourseMaterial,
    CourseStudentAssociation,
    CourseTestAssociation,
    MaterialFile,
    Profile as ProfileModel,
    Role,
)


async def get_categories(session: AsyncSession) -> list[CourseCategory]:
    result = await session.scalars(select(CourseCategory).order_by(CourseCategory.name))
    return list(result)


async def create_course(
    session: AsyncSession,
    name: str,
    description: str,
    user_id: int,
    category_id: Optional[int] = None,
):
    if category_id is not None and await session.get(CourseCategory, category_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Такого типа курса нет"
        )

    course = Course(
        name=name, description=description, teacher_id=user_id, category_id=category_id
    )
    session.add(course)
    await session.commit()
    return {"id": course.id}


async def get_list_course(
    session: AsyncSession,
    user_id: int,
    search: Optional[str],
    direct: Optional[int],
    sort_by: Optional[str],
    category_id: Optional[int] = None,
) -> list[CourseGet]:
    user = await get_profile(session=session, user_id=user_id)

    state = (
        select(Course)
        .options(selectinload(Course.tests).joinedload(CourseTestAssociation.test))
        .options(
            selectinload(Course.students).joinedload(CourseStudentAssociation.student)
        )
    )

    if user.role.name == "Преподаватель":
        state = state.where(Course.teacher_id == user_id)

    if user.role.name == "Студент":
        state = state.where(Course.students.any(CourseStudentAssociation.profile_id == user_id))
    
    if category_id is not None:
        state = state.where(Course.category_id == category_id)

    if search:
        state = state.where(
            or_(
                Course.name.ilike(f"%{search}%"),
                Course.description.ilike(f"%{search}%")
            )
        )

    order_func = asc if direct == 1 else desc

    sort_field = getattr(Course, sort_by or "name", Course.name)
    state = state.order_by(order_func(sort_field))

    result: Result = await session.execute(state)
    courses = result.scalars().all()
    return list(courses)


async def update_course(
    course: CourseGet, session: AsyncSession, course_update: CourseUpdatePartial
):
    for name, value in course_update.model_dump(exclude_unset=True).items():
        setattr(course, name, value)

    await session.commit()
    return course


async def add_test_in_course(
    tests_ids: Union[int, list[int]], session: AsyncSession, course
):
    tests = [
        await get_test(session=session, test_id=single_id) for single_id in tests_ids
    ]

    for test in tests:
        course.tests.append(CourseTestAssociation(test=test))

    await session.commit()


async def add_student_in_course(
    student_ids: Union[int, list[int]], session: AsyncSession, course
):
    students = [
        await crud_profile.get_profile(session=session, user_id=single_id)
        for single_id in student_ids
    ]

    for student in students:
        course.students.append(CourseStudentAssociation(student=student))

    await session.commit()


async def delete_student_in_course(student_id: int, session: AsyncSession, course):
    student = await crud_profile.get_profile(session=session, user_id=student_id)
    association_to_remove = next(
        (assoc for assoc in course.students if assoc.profile_id == student.id), None
    )

    if association_to_remove is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Студент не записан на этот курс",
        )

    await session.delete(association_to_remove)
    await session.commit()


async def delete_course(
    course: CourseGet,
    session: AsyncSession,
):
    stored_names = list(
        await session.scalars(
            select(MaterialFile.stored_name)
            .join(CourseMaterial, CourseMaterial.id == MaterialFile.material_id)
            .where(CourseMaterial.course_id == course.id)
        )
    )

    await session.delete(course)
    await session.commit()
    delete_files(stored_names)


async def get_catalog(
    session: AsyncSession,
    user_id: int,
    search: Optional[str],
    category_id: Optional[int],
) -> list[CatalogCourse]:
    """Все курсы платформы, независимо от того, участвует ли в них пользователь."""
    state = (
        select(Course)
        .options(selectinload(Course.tests))
        .options(selectinload(Course.students))
        .order_by(Course.name)
    )

    if category_id is not None:
        state = state.where(Course.category_id == category_id)

    if search:
        state = state.where(
            or_(
                Course.name.ilike(f"%{search}%"),
                Course.description.ilike(f"%{search}%"),
            )
        )

    courses = (await session.scalars(state)).all()
    return [
        CatalogCourse(
            id=course.id,
            name=course.name,
            description=course.description,
            category=course.category,
            teacher=ProfileGet.model_validate(course.teacher),
            students_count=len(course.students),
            tests_count=len(course.tests),
            is_member=course.teacher_id == user_id
            or any(assoc.profile_id == user_id for assoc in course.students),
        )
        for course in courses
    ]


async def enroll_student(session: AsyncSession, course_id: int, user_id: int):
    course = await session.get(Course, course_id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Курс не найден"
        )

    already = await session.scalar(
        select(CourseStudentAssociation.id).where(
            CourseStudentAssociation.course_id == course_id,
            CourseStudentAssociation.profile_id == user_id,
        )
    )
    if already is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Вы уже записаны на этот курс",
        )

    session.add(CourseStudentAssociation(course_id=course_id, profile_id=user_id))
    await session.commit()
    return {"id": course_id}


async def get_student_candidates(
    session: AsyncSession, course_id: int, search: Optional[str], limit: int = 50
):
    enrolled = select(CourseStudentAssociation.profile_id).where(
        CourseStudentAssociation.course_id == course_id
    )
    state = (
        select(ProfileModel)
        .join(Role, Role.id == ProfileModel.role_id)
        .where(Role.name == "Студент")
        .where(ProfileModel.id.not_in(enrolled))
        .order_by(ProfileModel.last_name, ProfileModel.first_name, ProfileModel.email)
        .limit(limit)
    )
    if search:
        pattern = f"%{search}%"
        state = state.where(
            or_(
                ProfileModel.email.ilike(pattern),
                ProfileModel.first_name.ilike(pattern),
                ProfileModel.last_name.ilike(pattern),
            )
        )
    return list((await session.scalars(state)).all())
