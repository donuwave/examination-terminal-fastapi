"""Фоновые задачи уведомлений."""

import logging
import time

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from api_v1.notification import service as notifications
from core.models import Course, CourseStudentAssociation, Test, TestProgress, db_helper

log = logging.getLogger(__name__)


async def notify_pause_over(session: AsyncSession) -> int:
    """Сообщает студентам, что пауза после проваленной попытки закончилась и можно пересдавать.

    Каждую попытку обрабатываем один раз (`pause_notified`). Уведомляем, только если попытка
    последняя, тест не сдан, обычные попытки ещё остались и пауза действительно была.
    """
    now = int(time.time())
    newer = aliased(TestProgress)
    due = (
        await session.scalars(
            select(TestProgress)
            .join(Test, Test.id == TestProgress.test_id)
            .where(
                TestProgress.status == 3,
                TestProgress.pause_notified.is_(False),
                TestProgress.finished_at.is_not(None),
                TestProgress.finished_at + Test.retry_delay_minutes * 60 <= now,
            )
        )
    ).all()

    sent = 0
    for attempt in due:
        attempt.pause_notified = True
        test = attempt.test
        if attempt.passed or test.retry_delay_minutes <= 0 or attempt.attempt_no >= test.max_attempts:
            continue

        # Новее есть попытка или тест уже сдан: пересдача либо идёт, либо не нужна.
        later = await session.scalar(
            select(
                exists().where(
                    newer.course_id == attempt.course_id,
                    newer.test_id == attempt.test_id,
                    newer.participant_id == attempt.participant_id,
                    (newer.id > attempt.id) | (newer.passed.is_(True)),
                )
            )
        )
        enrolled = await session.scalar(
            select(CourseStudentAssociation.id).where(
                CourseStudentAssociation.course_id == attempt.course_id,
                CourseStudentAssociation.profile_id == attempt.participant_id,
            )
        )
        if later or enrolled is None:
            continue

        course = await session.get(Course, attempt.course_id)
        await notifications.notify(
            session,
            attempt.participant_id,
            notifications.PAUSE_OVER,
            "Можно пересдать тест",
            f"Пауза закончилась: тест «{test.name}» в курсе «{course.name}» можно пройти снова",
            f"/courses/{attempt.course_id}",
        )
        sent += 1

    await session.commit()
    return sent


async def run_pause_over() -> None:
    try:
        async with db_helper.session_factory() as session:
            await notify_pause_over(session)
    except Exception:  # задача не должна падать и останавливать планировщик
        log.exception("Не удалось разослать уведомления об окончании паузы")
