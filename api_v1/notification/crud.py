from datetime import datetime
from typing import Dict, List

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.notification.service import ALL_KINDS
from core.models import Notification, NotificationPref


async def list_notifications(
    session: AsyncSession, user_id: int, limit: int, offset: int
) -> List[Notification]:
    return list(
        await session.scalars(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )


async def unread_count(session: AsyncSession, user_id: int) -> int:
    return (
        await session.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id, Notification.read_at.is_(None)
            )
        )
    ) or 0


async def mark_read(session: AsyncSession, user_id: int, notification_id: int) -> None:
    notification = await session.get(Notification, notification_id)
    if notification is None or notification.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уведомление не найдено")
    if notification.read_at is None:
        notification.read_at = datetime.now()
        await session.commit()


async def mark_all_read(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now())
    )
    await session.commit()


async def get_prefs(session: AsyncSession, user_id: int) -> Dict[str, bool]:
    rows = await session.execute(
        select(NotificationPref.kind, NotificationPref.enabled).where(
            NotificationPref.user_id == user_id
        )
    )
    saved = {kind: enabled for kind, enabled in rows.all()}
    return {kind: saved.get(kind, True) for kind in ALL_KINDS}


async def set_pref(session: AsyncSession, user_id: int, kind: str, enabled: bool) -> None:
    if kind not in ALL_KINDS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Неизвестный тип уведомления")
    pref = await session.scalar(
        select(NotificationPref).where(
            NotificationPref.user_id == user_id, NotificationPref.kind == kind
        )
    )
    if pref is None:
        session.add(NotificationPref(user_id=user_id, kind=kind, enabled=enabled))
    else:
        pref.enabled = enabled
    await session.commit()
