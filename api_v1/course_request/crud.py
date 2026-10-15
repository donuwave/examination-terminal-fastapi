from datetime import datetime
from typing import List

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.notification import service as notifications
from core.models import Course, CourseRequest, CourseStudentAssociation, Profile, Role, User
from core.models.course_request import (
    ACCEPTED,
    APPLICATION,
    CANCELLED,
    DECLINED,
    INVITATION,
    PENDING,
)


def _fail(code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


async def _is_member(session: AsyncSession, course_id: int, student_id: int) -> bool:
    return (
        await session.scalar(
            select(CourseStudentAssociation.id).where(
                CourseStudentAssociation.course_id == course_id,
                CourseStudentAssociation.profile_id == student_id,
            )
        )
        is not None
    )


async def _pending(session: AsyncSession, course_id: int, student_id: int) -> CourseRequest | None:
    return await session.scalar(
        select(CourseRequest).where(
            CourseRequest.course_id == course_id,
            CourseRequest.student_id == student_id,
            CourseRequest.status == PENDING,
        )
    )


async def _admit(session: AsyncSession, course_id: int, student_id: int) -> None:
    if not await _is_member(session, course_id, student_id):
        session.add(CourseStudentAssociation(course_id=course_id, profile_id=student_id))


async def _reload(session: AsyncSession, request: CourseRequest) -> CourseRequest:
    """Перечитываем запись вместе со связанными курсом и студентом, чтобы отдать её в ответ."""
    return await session.scalar(
        select(CourseRequest)
        .where(CourseRequest.id == request.id)
        .execution_options(populate_existing=True)
    )


def _close(request: CourseRequest, status_: str) -> None:
    request.status = status_
    request.decided_at = datetime.now()


async def apply(session: AsyncSession, course: Course, student_id: int) -> CourseRequest:
    """Студент подаёт заявку на курс, куда нельзя записаться сразу."""
    if course.enrollment != "request":
        raise _fail(status.HTTP_400_BAD_REQUEST, "На этот курс можно записаться сразу, заявка не нужна")
    if await _is_member(session, course.id, student_id):
        raise _fail(status.HTTP_400_BAD_REQUEST, "Вы уже записаны на этот курс")

    existing = await _pending(session, course.id, student_id)
    if existing is not None:
        detail = (
            "Вы уже подали заявку"
            if existing.kind == APPLICATION
            else "Преподаватель уже пригласил вас на этот курс: примите приглашение"
        )
        raise _fail(status.HTTP_409_CONFLICT, detail)

    request = CourseRequest(course_id=course.id, student_id=student_id, kind=APPLICATION)
    session.add(request)
    student = await session.get(Profile, student_id)
    await notifications.notify(
        session,
        course.teacher_id,
        notifications.NEW_APPLICATION,
        "Новая заявка на курс",
        f"{notifications.person_name(student)} хочет записаться на курс «{course.name}»",
        f"/courses/{course.id}",
        actor_id=student.id,
    )
    await session.commit()
    return await _reload(session, request)


async def cancel_application(session: AsyncSession, course_id: int, student_id: int) -> None:
    request = await _pending(session, course_id, student_id)
    if request is None or request.kind != APPLICATION:
        raise _fail(status.HTTP_404_NOT_FOUND, "Активной заявки нет")
    _close(request, CANCELLED)
    await session.commit()


async def invite(session: AsyncSession, course: Course, email: str) -> CourseRequest:
    """Преподаватель приглашает студента по почте. Записать его без согласия нельзя."""
    student = await session.scalar(
        select(Profile).join(Role, Role.id == Profile.role_id).where(
            func.lower(Profile.email) == email.lower(), Role.name == "Студент"
        )
    )
    if student is None:
        raise _fail(status.HTTP_404_NOT_FOUND, "Студент с такой почтой не найден")
    if await _is_member(session, course.id, student.id):
        raise _fail(status.HTTP_400_BAD_REQUEST, "Студент уже на курсе")

    existing = await _pending(session, course.id, student.id)
    if existing is not None:
        detail = (
            "Приглашение уже отправлено"
            if existing.kind == INVITATION
            else "Студент уже подал заявку: одобрите её"
        )
        raise _fail(status.HTTP_409_CONFLICT, detail)

    request = CourseRequest(course_id=course.id, student_id=student.id, kind=INVITATION)
    session.add(request)
    teacher = await session.get(Profile, course.teacher_id)
    await notifications.notify(
        session,
        student.id,
        notifications.INVITATION,
        "Приглашение на курс",
        f"{notifications.person_name(teacher)} приглашает вас на курс «{course.name}»",
        "/",
        actor_id=teacher.id,
    )
    await session.commit()
    return await _reload(session, request)


async def list_for_course(session: AsyncSession, course_id: int) -> List[CourseRequest]:
    """Ожидающие решения заявки и приглашения курса."""
    return list(
        await session.scalars(
            select(CourseRequest)
            .where(CourseRequest.course_id == course_id, CourseRequest.status == PENDING)
            .order_by(CourseRequest.id)
        )
    )


async def _get_pending_of_course(session: AsyncSession, course_id: int, request_id: int) -> CourseRequest:
    request = await session.get(CourseRequest, request_id)
    if request is None or request.course_id != course_id or request.status != PENDING:
        raise _fail(status.HTTP_404_NOT_FOUND, "Заявка не найдена или уже обработана")
    return request


async def decide_application(
    session: AsyncSession, course_id: int, request_id: int, approve: bool
) -> CourseRequest:
    request = await _get_pending_of_course(session, course_id, request_id)
    if request.kind != APPLICATION:
        raise _fail(status.HTTP_400_BAD_REQUEST, "Это приглашение, а не заявка студента")
    if approve:
        await _admit(session, course_id, request.student_id)
    _close(request, ACCEPTED if approve else DECLINED)
    await notifications.notify(
        session,
        request.student_id,
        notifications.APPLICATION_DECIDED,
        "Заявка одобрена" if approve else "Заявка отклонена",
        f"Преподаватель {'одобрил' if approve else 'отклонил'} вашу заявку на курс «{request.course.name}»",
        f"/courses/{course_id}" if approve else "/courses?scope=all",
    )
    await session.commit()
    return request


async def cancel_invitation(session: AsyncSession, course_id: int, request_id: int) -> None:
    request = await _get_pending_of_course(session, course_id, request_id)
    if request.kind != INVITATION:
        raise _fail(status.HTTP_400_BAD_REQUEST, "Это заявка студента: одобрите или отклоните её")
    _close(request, CANCELLED)
    await session.commit()


async def invitations_of(session: AsyncSession, student_id: int) -> List[CourseRequest]:
    return list(
        await session.scalars(
            select(CourseRequest)
            .where(
                CourseRequest.student_id == student_id,
                CourseRequest.kind == INVITATION,
                CourseRequest.status == PENDING,
            )
            .order_by(CourseRequest.id.desc())
        )
    )


async def answer_invitation(
    session: AsyncSession, request_id: int, student_id: int, accept: bool
) -> CourseRequest:
    request = await session.get(CourseRequest, request_id)
    if (
        request is None
        or request.student_id != student_id
        or request.kind != INVITATION
        or request.status != PENDING
    ):
        raise _fail(status.HTTP_404_NOT_FOUND, "Приглашение не найдено или уже обработано")
    if accept:
        await _admit(session, request.course_id, student_id)
    _close(request, ACCEPTED if accept else DECLINED)
    await notifications.notify(
        session,
        request.course.teacher_id,
        notifications.INVITATION_ANSWERED,
        "Ответ на приглашение",
        f"{notifications.person_name(request.student)} "
        f"{'принял приглашение на курс' if accept else 'отклонил приглашение на курс'} «{request.course.name}»",
        f"/courses/{request.course_id}",
        actor_id=request.student_id,
    )
    await session.commit()
    return request


async def pending_by_course(session: AsyncSession, student_id: int) -> dict[int, str]:
    """Для каталога: по каким курсам у студента есть ожидающая заявка или приглашение."""
    rows = await session.execute(
        select(CourseRequest.course_id, CourseRequest.kind).where(
            CourseRequest.student_id == student_id, CourseRequest.status == PENDING
        )
    )
    return {course_id: kind for course_id, kind in rows.all()}
