from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api_v1.auth.dependencies import get_user_id_in_access_token
from core.models import db_helper, Test, TestQuestionAssociation


async def get_test(
    test_id: int, session: AsyncSession = Depends(db_helper.scoped_session_dependency)
):
    return await session.scalar(
        select(Test)
        .where(Test.id == test_id)
        .options(
            selectinload(Test.questions).joinedload(TestQuestionAssociation.question)
        )
    )


async def get_own_test(
    test=Depends(get_test), user_id: int = Depends(get_user_id_in_access_token)
):
    """Тест, которым распоряжается его автор. Ответы и правки доступны только ему."""
    if test is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тест не найден")
    if test.creator_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваш тест")
    return test
