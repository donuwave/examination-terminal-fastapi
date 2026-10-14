from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import crud as auth_crud
from ..auth.dependencies import (
    validate_auth_user,
    register_user,
    create_tokens_by_auth,
    get_current_auth_user_for_refresh,
    get_user_id_in_access_token,
)
from ..auth.schemas import AuthBase, PasswordChange
from ..auth.utils import hash_password, validate_password
from core.models import User, db_helper
from core.rate_limit import password_limiter

router = APIRouter(tags=["Auth"])


@router.post("/login", response_model=AuthBase)
async def auth_login(
    user: User = Depends(validate_auth_user),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await create_tokens_by_auth(user=user, session=session)


@router.post("/registration")
async def auth_registration(
    user: User = Depends(register_user),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await create_tokens_by_auth(user=user, session=session)


@router.post("/refresh", response_model=AuthBase, response_model_exclude_none=True)
async def auth_refresh(user: User = Depends(get_current_auth_user_for_refresh), session: AsyncSession = Depends(db_helper.scoped_session_dependency)):
    return await create_tokens_by_auth(user=user, session=session)


# @router.get("/")
# async def auth(session: AsyncSession = Depends(db_helper.scoped_session_dependency)):
#     state = select(User).order_by(User.id)
#     result: Result = await session.execute(state)
#     users = result.scalars().all()
#     return list(users)


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
