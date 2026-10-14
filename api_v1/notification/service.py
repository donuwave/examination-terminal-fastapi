"""Создание уведомлений. Вызывается из мест, где что-то произошло.

`notify` только добавляет запись в сессию и не делает commit: она сохранится вместе
с действием, которое её вызвало. Если пользователь отключил такой тип уведомлений, запись не создаётся.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Notification, NotificationPref, Profile

# Типы уведомлений и кому они адресованы.
INVITATION = "invitation"
APPLICATION_DECIDED = "application_decided"
PAUSE_OVER = "pause_over"
EXTRA_ATTEMPT = "extra_attempt"
REMOVED = "removed"
NEW_APPLICATION = "new_application"
ATTEMPTS_OUT = "attempts_out"
INVITATION_ANSWERED = "invitation_answered"
COURSE_FINISHED = "course_finished"

STUDENT_KINDS = (INVITATION, APPLICATION_DECIDED, PAUSE_OVER, EXTRA_ATTEMPT, REMOVED)
TEACHER_KINDS = (NEW_APPLICATION, ATTEMPTS_OUT, INVITATION_ANSWERED, COURSE_FINISHED)
ALL_KINDS = STUDENT_KINDS + TEACHER_KINDS


def person_name(person: Profile) -> str:
    full = " ".join(part for part in (person.first_name, person.last_name) if part)
    return full or person.email


async def is_enabled(session: AsyncSession, user_id: int, kind: str) -> bool:
    enabled = await session.scalar(
        select(NotificationPref.enabled).where(
            NotificationPref.user_id == user_id, NotificationPref.kind == kind
        )
    )
    return True if enabled is None else enabled


async def notify(
    session: AsyncSession,
    user_id: int,
    kind: str,
    title: str,
    text: str,
    link: str | None = None,
) -> None:
    if not await is_enabled(session, user_id, kind):
        return
    session.add(Notification(user_id=user_id, kind=kind, title=title, text=text, link=link))
