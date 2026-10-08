from sqlalchemy import select, Result
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.course_test.schemas import TestGet

from api_v1.questions import crud as crud_question
from core.models import Test, TestQuestionAssociation


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
    for question_in in questions:
        question = await crud_question.create_question(
            session=session, question_in=question_in
        )
        test.questions.append(TestQuestionAssociation(question=question))

    await session.commit()
