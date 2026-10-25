from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import crud as auth_crud
from ..auth import emails, reset
from ..auth.dependencies import (
    validate_auth_user,
    register_user,
    create_tokens_by_auth,
    get_current_auth_user_for_refresh,
    get_user_id_in_access_token,
)
from ..auth.schemas import AuthBase, PasswordChange, ResetConfirm, ResetRequest, ResetVerify
from ..auth.utils import hash_password, validate_password
from core.models import User, db_helper
from core import mail
from core.rate_limit import (
    password_limiter,
    reset_check_limiter,
    reset_email_limiter,
    reset_ip_limiter,
)

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


def _client(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/reset/request", status_code=status.HTTP_204_NO_CONTENT)
async def reset_request(
    data: ResetRequest,
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Отправляет код на почту. Ответ один и тот же для любой почты."""
    email = data.email.lower()
    ip = _client(request)
    reset_email_limiter.check(email)
    reset_ip_limiter.check(ip)
    reset_email_limiter.hit(email)
    reset_ip_limiter.hit(ip)

    user = await reset.get_user(session, data.email)
    if user is not None:
        code = await reset.issue_code(session, user)
        background.add_task(
            mail.send, emails.reset_code_mail(user.email, code, reset.CODE_LIFETIME_MINUTES)
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset/verify", status_code=status.HTTP_204_NO_CONTENT)
async def reset_verify(
    data: ResetVerify,
    request: Request,
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Проверяет код, не расходуя его: следом тот же код понадобится для смены пароля."""
    key = f"{data.email.lower()}|{_client(request)}"
    reset_check_limiter.check(key)
    try:
        await reset.check_code(session, data.email, data.code)
    except HTTPException:
        reset_check_limiter.hit(key)
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def reset_confirm(
    data: ResetConfirm,
    request: Request,
    background: BackgroundTasks,
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Меняет пароль по коду из письма. Код после этого перестаёт действовать."""
    key = f"{data.email.lower()}|{_client(request)}"
    reset_check_limiter.check(key)
    try:
        user, record = await reset.check_code(session, data.email, data.code)
    except HTTPException:
        reset_check_limiter.hit(key)
        raise
    await reset.set_new_password(session, user, record, data.password)
    background.add_task(mail.send, emails.password_changed_mail(user.email))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
