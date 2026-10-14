from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.questions.schemas import QuestionUpdatePartial, check_question
from core.models import Question


async def create_question(session: AsyncSession, question_in):
    question = Question(
        text_question=question_in.text_question,
        kind=question_in.kind,
        options=question_in.options,
        correct_answer=question_in.correct_answer,
        correct_answers=question_in.correct_answers,
    )
    session.add(question)
    await session.flush()
    return question


async def update_question(
    question_update: QuestionUpdatePartial, session: AsyncSession, question: Question
):
    """Меняет переданные поля. Проверяем вопрос целиком: он должен остаться корректным после правки."""
    changes = question_update.model_dump(exclude_unset=True, exclude_none=True)
    kind = changes.get("kind", question.kind)
    # Если меняют варианты или тип, но не говорят, какие верные, прежние верные ответы пересматривать не будем.
    if "correct_answers" in changes or "correct_answer" in changes:
        correct_answers = changes.get("correct_answers")
        correct_answer = changes.get("correct_answer")
    else:
        correct_answers = list(question.correct_answers) or [question.correct_answer]
        correct_answer = None
    try:
        text, options, first, correct = check_question(
            kind,
            changes.get("text_question", question.text_question),
            changes.get("options", question.options),
            correct_answer,
            correct_answers,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error))

    question.text_question, question.kind = text, kind
    question.options, question.correct_answer, question.correct_answers = options, first, correct
    await session.commit()
    return question
