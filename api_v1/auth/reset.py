"""Сброс пароля по коду из письма.

Правила:
- ответ на запрос кода одинаков, есть такая почта или нет, чтобы по ответу нельзя было перебирать адреса;
- код шестизначный, живёт 15 минут, хранится только хэшем;
- после 5 неверных вводов код сгорает;
- после сброса старые токены перестают продлевать сессию.
"""

import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.utils import hash_password, validate_password
from core.models import PasswordReset, User

CODE_LENGTH = 6
CODE_LIFETIME_MINUTES = 15
MAX_ATTEMPTS = 5

INVALID = "Неверный код или он устарел"


def new_code() -> str:
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


async def get_user(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def issue_code(session: AsyncSession, user: User) -> str:
    """Выдаёт новый код, прежние неиспользованные коды этого пользователя перестают работать."""
    await session.execute(
        delete(PasswordReset).where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
    )
    code = new_code()
    session.add(
        PasswordReset(
            user_id=user.id,
            code_hash=hash_password(code),
            expires_at=datetime.utcnow() + timedelta(minutes=CODE_LIFETIME_MINUTES),
        )
    )
    await session.commit()
    return code


async def check_code(session: AsyncSession, email: str, code: str) -> tuple[User, PasswordReset]:
    """Проверяет код. Неверный код и несуществующая почта дают один и тот же ответ."""
    user = await get_user(session, email)
    reset = None
    if user is not None:
        reset = await session.scalar(
            select(PasswordReset)
            .where(PasswordReset.user_id == user.id, PasswordReset.used_at.is_(None))
            .order_by(PasswordReset.id.desc())
            .limit(1)
        )
    if user is None or reset is None or reset.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID)
    if reset.attempts >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Слишком много неверных попыток. Запросите новый код",
        )
    if not validate_password(code, reset.code_hash):
        reset.attempts += 1
        await session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID)
    return user, reset


async def set_new_password(
    session: AsyncSession, user: User, reset: PasswordReset, password: str
) -> None:
    now = datetime.utcnow()
    user.password = hash_password(password)
    # Без долей секунды: iat токена тоже целое число секунд.
    user.password_changed_at = now.replace(microsecond=0)
    reset.used_at = now
    await session.commit()
