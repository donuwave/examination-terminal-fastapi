from typing import Optional

from fastapi import Depends, HTTPException, status
from pydantic import EmailStr
from sqlalchemy import Result, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from api_v1.profile.schemas import ProfileGet, ProfileUpdate
from core.models import (
    Course,
    CourseStudentAssociation,
    Profile,
    Test,
    TestExtraAttempt,
    TestProgress,
    User,
    db_helper,
)
from core.models.test_progress import TestProgressResult


async def create_profile(session: AsyncSession, role_id: int, email: EmailStr):
    profile = Profile(email=email, role_id=role_id)
    session.add(profile)
    await session.commit()
    return profile


async def get_list_profile(
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
) -> list[ProfileGet]:
    state = select(Profile).options(joinedload(Profile.role)).order_by(Profile.id)
    result: Result = await session.execute(state)
    profiles = result.scalars().all()
    return list(profiles)


async def get_profile(user_id: int, session: AsyncSession) -> ProfileGet:
    state = (
        select(Profile).options(joinedload(Profile.role)).where(Profile.id == user_id)
    )
    results = await session.scalars(state)
    profile = next(results, None)

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Профиль не найден"
        )

    return profile


async def update_profile(
    profile_update: ProfileUpdate, session: AsyncSession, user_id: int
):
    current_profile = await get_profile(user_id=user_id, session=session)
    update_data = profile_update.model_dump(exclude_unset=True).items()

    for name, value in update_data:
        setattr(current_profile, name, value)

    await session.commit()
    return current_profile


async def delete_account(session: AsyncSession, user_id: int) -> None:
    """Удаляет аккаунт вместе с записями на курсы и попытками.

    Преподавателя с курсами или тестами не удаляем: они остались бы без автора,
    а студенты потеряли бы курс. Сначала курсы нужно удалить.
    """
    await get_profile(user_id=user_id, session=session)

    owns_course = await session.scalar(select(Course.id).where(Course.teacher_id == user_id).limit(1))
    owns_test = await session.scalar(select(Test.id).where(Test.creator_id == user_id).limit(1))
    if owns_course is not None or owns_test is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сначала удалите свои курсы и тесты",
        )

    attempt_ids = select(TestProgress.id).where(TestProgress.participant_id == user_id)
    await session.execute(
        delete(TestProgressResult).where(TestProgressResult.test_progress_id.in_(attempt_ids))
    )
    await session.execute(delete(TestProgress).where(TestProgress.participant_id == user_id))
    await session.execute(delete(TestExtraAttempt).where(TestExtraAttempt.student_id == user_id))
    await session.execute(
        delete(CourseStudentAssociation).where(CourseStudentAssociation.profile_id == user_id)
    )
    await session.execute(delete(User).where(User.profile_id == user_id))
    await session.execute(delete(Profile).where(Profile.id == user_id))
    await session.commit()
