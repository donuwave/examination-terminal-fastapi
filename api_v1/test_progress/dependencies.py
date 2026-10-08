from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.test_progress.rules import sync_state
from core.models import TestProgress, db_helper


async def get_progress_test(
    progress_test_id: int,
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
) -> TestProgress:
    progress = await session.scalar(
        select(TestProgress)
        .where(TestProgress.id == progress_test_id)
        .options(selectinload(TestProgress.result_test))
    )
    if progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Попытка не найдена")
    return await sync_state(session, progress)
