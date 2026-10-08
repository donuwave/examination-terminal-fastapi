"""Прогресс студента по курсу: какие разделы открыты и сданы."""

from dataclasses import dataclass
from typing import Dict, List, Literal, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.test_progress.rules import compute_state, load_attempts, load_extras
from api_v1.test_progress.schemas import TestState
from core.models import CourseSection, CourseTestAssociation, Test

SectionStatus = Literal["open", "passed", "locked"]


@dataclass
class SectionProgress:
    section: CourseSection
    tests: List[Test]
    status: SectionStatus


@dataclass
class CourseProgress:
    sections: List[SectionProgress]
    test_states: Dict[int, TestState]

    @property
    def unlocked_ids(self) -> Set[int]:
        return {item.section.id for item in self.sections if item.status != "locked"}

    @property
    def passed_count(self) -> int:
        return sum(1 for item in self.sections if item.status == "passed")


async def course_progress(session: AsyncSession, course_id: int, student_id: int) -> CourseProgress:
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

    attempts = await load_attempts(session, course_id, student_id)
    extras = await load_extras(session, course_id, student_id)

    states = {
        assoc.test_id: compute_state(assoc.test, attempts.get(assoc.test_id, []), extras.get(assoc.test_id, 0))
        for assoc in associations
        if assoc.section_id is not None
    }

    result: List[SectionProgress] = []
    previous_passed = True
    for section in sections:
        tests = [a.test for a in associations if a.section_id == section.id]
        passed = all(states[test.id].status == "passed" for test in tests)
        if not previous_passed:
            status: SectionStatus = "locked"
        else:
            status = "passed" if passed else "open"
        result.append(SectionProgress(section=section, tests=tests, status=status))
        previous_passed = previous_passed and passed

    return CourseProgress(sections=result, test_states=states)


async def unlocked_section_ids(session: AsyncSession, course_id: int, student_id: int) -> Set[int]:
    return (await course_progress(session, course_id, student_id)).unlocked_ids
