from typing import List

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.course_material.storage import delete_files
from api_v1.course_section.schemas import SectionGet, SectionTest
from api_v1.course_section.state import course_progress
from api_v1.test_progress.schemas import TestState
from core.models import (
    CourseMaterial,
    CourseSection,
    CourseTestAssociation,
    MaterialFile,
    Test,
    TestProgress,
)


async def get_section(session: AsyncSession, course_id: int, section_id: int) -> CourseSection:
    section = await session.get(CourseSection, section_id)
    if section is None or section.course_id != course_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Раздел не найден")
    return section


def _section_test(test: Test, state: TestState | None) -> SectionTest:
    return SectionTest(
        id=test.id,
        name=test.name,
        time_limit=test.time_limit,
        questions_count=len(test.questions),
        pass_percent=test.pass_percent,
        max_attempts=test.max_attempts,
        retry_delay_minutes=test.retry_delay_minutes,
        state=state,
    )


async def list_sections(
    session: AsyncSession, course_id: int, viewer_id: int, is_teacher: bool
) -> List[SectionGet]:
    """Разделы курса. Студенту закрытые разделы приходят без содержимого."""
    sections = (
        await session.scalars(
            select(CourseSection)
            .where(CourseSection.course_id == course_id)
            .order_by(CourseSection.position, CourseSection.id)
        )
    ).all()

    associations = (
        await session.scalars(
            select(CourseTestAssociation)
            .where(CourseTestAssociation.course_id == course_id)
            .options(selectinload(CourseTestAssociation.test).selectinload(Test.questions))
            .order_by(CourseTestAssociation.id)
        )
    ).all()
    tests_by_section: dict[int, list[Test]] = {}
    for assoc in associations:
        if assoc.section_id is not None:
            tests_by_section.setdefault(assoc.section_id, []).append(assoc.test)

    progress = None if is_teacher else await course_progress(session, course_id, viewer_id)
    status_by_section = (
        {item.section.id: item.status for item in progress.sections} if progress else {}
    )

    result: List[SectionGet] = []
    for section in sections:
        tests = tests_by_section.get(section.id, [])
        status = status_by_section.get(section.id)
        locked = status == "locked"
        result.append(
            SectionGet(
                id=section.id,
                course_id=section.course_id,
                title=section.title,
                position=section.position,
                materials=[] if locked else section.materials,
                tests=[]
                if locked
                else [_section_test(test, progress.test_states.get(test.id) if progress else None) for test in tests],
                materials_count=len(section.materials),
                tests_count=len(tests),
                locked=locked,
                status=status,
            )
        )
    return result


async def create_section(session: AsyncSession, course_id: int, title: str) -> CourseSection:
    last = await session.scalar(
        select(func.max(CourseSection.position)).where(CourseSection.course_id == course_id)
    )
    section = CourseSection(
        course_id=course_id, title=title.strip(), position=(last + 1) if last is not None else 0
    )
    session.add(section)
    await session.commit()
    return section


async def rename_section(session: AsyncSession, section: CourseSection, title: str) -> None:
    section.title = title.strip()
    await session.commit()


async def delete_section(session: AsyncSession, section: CourseSection) -> None:
    """Удаляет раздел с материалами и убирает его тесты из курса."""
    stored_names = list(
        await session.scalars(
            select(MaterialFile.stored_name)
            .join(CourseMaterial, CourseMaterial.id == MaterialFile.material_id)
            .where(CourseMaterial.section_id == section.id)
        )
    )

    associations = (
        await session.scalars(
            select(CourseTestAssociation).where(CourseTestAssociation.section_id == section.id)
        )
    ).all()
    for assoc in associations:
        started = await session.scalar(
            select(TestProgress.id)
            .where(TestProgress.test_id == assoc.test_id, TestProgress.course_id == section.course_id)
            .limit(1)
        )
        if started is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="В разделе есть тест, который студенты уже проходили. Раздел удалить нельзя",
            )
        await session.delete(assoc)

    await session.delete(section)
    await session.commit()
    delete_files(stored_names)


async def reorder_sections(session: AsyncSession, course_id: int, ids: List[int]) -> None:
    sections = (
        await session.scalars(select(CourseSection).where(CourseSection.course_id == course_id))
    ).all()
    if set(ids) != {section.id for section in sections} or len(ids) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нужно передать все разделы курса ровно по одному разу",
        )
    by_id = {section.id: section for section in sections}
    for position, section_id in enumerate(ids):
        by_id[section_id].position = position
    await session.commit()


async def add_tests(
    session: AsyncSession, section: CourseSection, test_ids: List[int], author_id: int
) -> None:
    """Добавлять в курс можно только свои тесты: чужой тест нельзя ни подключить, ни подсмотреть."""
    for test_id in test_ids:
        test = await session.get(Test, test_id)
        if test is None or test.creator_id != author_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тест не найден")

        assoc = await session.scalar(
            select(CourseTestAssociation).where(
                CourseTestAssociation.course_id == section.course_id,
                CourseTestAssociation.test_id == test_id,
            )
        )
        if assoc is None:
            session.add(
                CourseTestAssociation(
                    course_id=section.course_id, test_id=test_id, section_id=section.id
                )
            )
        else:
            assoc.section_id = section.id
    await session.commit()


async def remove_test(session: AsyncSession, section: CourseSection, test_id: int) -> None:
    """Убирает тест из раздела. Попытки студентов остаются в истории, даже если тест уже проходили."""
    assoc = await session.scalar(
        select(CourseTestAssociation).where(
            CourseTestAssociation.course_id == section.course_id,
            CourseTestAssociation.test_id == test_id,
            CourseTestAssociation.section_id == section.id,
        )
    )
    if assoc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Теста нет в этом разделе")

    await session.delete(assoc)
    await session.commit()
