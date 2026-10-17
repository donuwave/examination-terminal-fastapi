from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import TestExtraAttempt, TestProgress
from core.models.test_progress import TestProgressResult


async def delete_attempts(
    session: AsyncSession, test_id: int, course_id: Optional[int] = None
) -> None:
    """Удаляет попытки студентов по тесту (в одном курсе или везде) вместе с ответами и доп. попытками.

    Без commit: вызывающий код сохраняет всё одной транзакцией.
    """
    attempts = select(TestProgress.id).where(TestProgress.test_id == test_id)
    progress = delete(TestProgress).where(TestProgress.test_id == test_id)
    extra = delete(TestExtraAttempt).where(TestExtraAttempt.test_id == test_id)
    if course_id is not None:
        attempts = attempts.where(TestProgress.course_id == course_id)
        progress = progress.where(TestProgress.course_id == course_id)
        extra = extra.where(TestExtraAttempt.course_id == course_id)
    await session.execute(
        delete(TestProgressResult).where(TestProgressResult.test_progress_id.in_(attempts))
    )
    await session.execute(progress)
    await session.execute(extra)
