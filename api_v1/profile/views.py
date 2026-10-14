from datetime import datetime

from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth import crud as auth_crud
from api_v1.auth.dependencies import create_tokens_by_auth, get_user_id_in_access_token
from api_v1.auth.schemas import AuthBase, PasswordChange
from api_v1.auth.utils import hash_password, validate_password
from api_v1.profile import crud as profile_crud
from api_v1.profile import public_crud
from api_v1.profile.public_schemas import PrivateProfile, ProfileCourses, PublicProfile
from api_v1.profile.schemas import ProfileGet, ProfileUpdate
from core.models import db_helper
from core.rate_limit import password_limiter

http_bearer = HTTPBearer()
router = APIRouter(tags=["Profile"], dependencies=[Depends(http_bearer)])


@router.get("/me", response_model=ProfileGet)
async def get_profile(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await profile_crud.get_profile(session=session, user_id=user_id)


@router.patch("/", response_model=ProfileGet)
async def update_profile(
    profile_update: ProfileUpdate,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await profile_crud.update_profile(
        profile_update=profile_update, session=session, user_id=user_id
    )


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Удаляет аккаунт текущего пользователя."""
    await profile_crud.delete_account(session=session, user_id=user_id)


@router.post("/password", response_model=AuthBase, response_model_exclude_none=True)
async def change_password(
    data: PasswordChange,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Смена пароля. Старые токены перестают продлевать сессию, текущей выдаются новые."""
    key = f"password:{user_id}"
    password_limiter.check(key)

    user = await auth_crud.get_item_user_by_id(session=session, user_id=user_id)
    if user is None or not validate_password(data.old_password, user.password):
        password_limiter.hit(key)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Старый пароль неверен")
    if data.old_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Новый пароль совпадает со старым"
        )

    user.password = hash_password(data.new_password)
    # Без долей секунды: iat токена тоже целое число секунд, иначе новые токены сочтутся старыми.
    user.password_changed_at = datetime.utcnow().replace(microsecond=0)
    await session.commit()
    password_limiter.reset(key)
    return await create_tokens_by_auth(user=user, session=session)


# Маршруты с числом в пути стоят после /me и /password, иначе они перехватят эти адреса.
@router.get("/{profile_id}", response_model=Union[PrivateProfile, PublicProfile])
async def get_other_profile(
    profile_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Профиль другого пользователя. Что видно, зависит от того, кто смотрит."""
    return await public_crud.get_profile_card(session, user_id, profile_id)


@router.get("/{profile_id}/courses", response_model=ProfileCourses)
async def get_other_profile_courses(
    profile_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Курсы преподавателя или студента с учётом прав смотрящего."""
    return await public_crud.get_profile_courses(session, user_id, profile_id, limit, offset)
