from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.questions.schemas import QuestionUpdatePartial, check_question
from core.models import Question


async def create_question(session: AsyncSession, question_in):
    question = Question(
        text_question=question_in.text_question,
        options=question_in.options,
        correct_answer=question_in.correct_answer,
    )
    session.add(question)
    await session.flush()
    return question


async def update_question(
    question_update: QuestionUpdatePartial, session: AsyncSession, question: Question
):
    """Меняет переданные поля. Проверяем вопрос целиком: правильный ответ должен остаться вариантом."""
    changes = question_update.model_dump(exclude_unset=True, exclude_none=True)
    try:
        text, options, correct = check_question(
            changes.get("text_question", question.text_question),
            changes.get("options", question.options),
            changes.get("correct_answer", question.correct_answer),
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    question.text_question, question.options, question.correct_answer = text, options, correct
    await session.commit()
    return question
