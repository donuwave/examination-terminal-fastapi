from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.test_progress.crud import sync_state
from core.models import TestProgress, db_helper


async def get_progress_test(
    progress_test_id: Optional[int] = None,
    test_id: Optional[int] = None,
    course_id: Optional[int] = None,
    user_id: Optional[int] = None,
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    state = select(TestProgress).options(selectinload(TestProgress.result_test))

    if user_id:
        state = state.where(TestProgress.participant_id == user_id)

    if progress_test_id:
        state = state.where(TestProgress.id == progress_test_id)

    if test_id:
        state = state.where(TestProgress.test_id == test_id)

    if course_id:
        state = state.where(TestProgress.course_id == course_id)

    progress = await session.scalar(state)

    if not progress:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Попытка не найдена"
        )

    return await sync_state(session, progress)
