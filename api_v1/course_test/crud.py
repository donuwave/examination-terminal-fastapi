from fastapi import HTTPException, status
from sqlalchemy import Result, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.course_test.schemas import TestGet, TestUpdate

from api_v1.questions import crud as crud_question
from core.models import (
    Course,
    CourseSection,
    CourseTestAssociation,
    Question,
    Test,
    TestExtraAttempt,
    TestProgress,
    TestQuestionAssociation,
)


async def get_list_test(session: AsyncSession, user_id: int):
    state = (
        select(Test)
        .where(Test.creator_id == user_id)
        .options(
            selectinload(Test.questions).joinedload(TestQuestionAssociation.question)
        )
    )
    result: Result = await session.execute(state)
    tests = result.scalars().all()
    return list(tests)


async def get_placements(session: AsyncSession, user_id: int):
    """Где лежит каждый тест автора: курс и раздел."""
    rows = await session.execute(
        select(
            CourseTestAssociation.test_id,
            Course.id,
            Course.name,
            CourseSection.id,
            CourseSection.title,
        )
        .join(Test, Test.id == CourseTestAssociation.test_id)
        .join(Course, Course.id == CourseTestAssociation.course_id)
        .outerjoin(CourseSection, CourseSection.id == CourseTestAssociation.section_id)
        .where(Test.creator_id == user_id)
        .order_by(Course.name, CourseSection.position)
    )
    return [
        {
            "test_id": test_id,
            "course_id": course_id,
            "course_name": course_name,
            "section_id": section_id,
            "section_title": section_title,
        }
        for test_id, course_id, course_name, section_id, section_title in rows.all()
    ]


async def create_test(
    session: AsyncSession,
    user_id: int,
    name: str,
    time_limit: int,
    pass_percent: int = 60,
    max_attempts: int = 2,
    retry_delay_minutes: int = 120,
):
    test = Test(
        name=name,
        time_limit=time_limit,
        creator_id=user_id,
        pass_percent=pass_percent,
        max_attempts=max_attempts,
        retry_delay_minutes=retry_delay_minutes,
    )
    session.add(test)
    await session.commit()
    return {"id": test.id, "name": test.name, "time_limit": test.time_limit}


async def add_questions_in_test(
    test: TestGet,
    session: AsyncSession,
    questions,
):
    """Добавляет вопросы в конец теста и возвращает их id в порядке отправки."""
    position = max((assoc.position for assoc in test.questions), default=0)
    created = []
    for question_in in questions:
        question = await crud_question.create_question(
            session=session, question_in=question_in
        )
        position += 1
        test.questions.append(TestQuestionAssociation(question=question, position=position))
        created.append({"id": question.id})

    await session.commit()
    return created


async def update_test(session: AsyncSession, test: Test, data: TestUpdate) -> Test:
    for name, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(test, name, value)
    await session.commit()
    return test


async def delete_test(session: AsyncSession, test: Test) -> None:
    """Удаляет тест вместе с вопросами. Тест с попытками студентов не трогаем, чтобы не потерять их результаты."""
    attempts = await session.scalar(
        select(func.count(TestProgress.id)).where(TestProgress.test_id == test.id)
    )
    if attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="У теста есть попытки студентов. Уберите его из разделов, а не удаляйте",
        )

    question_ids = [assoc.question_id for assoc in test.questions]
    await session.execute(delete(CourseTestAssociation).where(CourseTestAssociation.test_id == test.id))
    await session.execute(delete(TestExtraAttempt).where(TestExtraAttempt.test_id == test.id))
    await session.execute(delete(TestQuestionAssociation).where(TestQuestionAssociation.test_id == test.id))
    if question_ids:
        await session.execute(delete(Question).where(Question.id.in_(question_ids)))
    await session.execute(delete(Test).where(Test.id == test.id))
    await session.commit()


def find_question(test: Test, question_id: int) -> Question:
    for assoc in test.questions:
        if assoc.question_id == question_id:
            return assoc.question
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Вопроса нет в этом тесте")


async def delete_question(session: AsyncSession, test: Test, question_id: int) -> None:
    question = find_question(test, question_id)
    await session.execute(
        delete(TestQuestionAssociation).where(TestQuestionAssociation.question_id == question.id)
    )
    await session.execute(delete(Question).where(Question.id == question.id))
    await session.commit()


async def reorder_questions(session: AsyncSession, test: Test, ids: list[int]) -> None:
    """Задаёт порядок вопросов. Передать нужно все вопросы теста, без лишних и повторов."""
    current = {assoc.question_id: assoc for assoc in test.questions}
    if len(ids) != len(set(ids)) or set(ids) != set(current):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Нужно передать все вопросы теста по одному разу",
        )
    for position, question_id in enumerate(ids, start=1):
        current[question_id].position = position
    await session.commit()
