from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api_v1.test_progress.crud import sync_state
from core.models import TestProgress, db_helper


async def scheduled_test_progress_overdue(progress_test_id: int):
    """В момент дедлайна: не начатый тест просрочен, начатый засчитывается."""
    async with db_helper.session_factory() as session:
        progress = await session.scalar(
            select(TestProgress)
            .where(TestProgress.id == progress_test_id)
            .options(selectinload(TestProgress.result_test))
        )
        if progress is not None:
            await sync_state(session, progress)
