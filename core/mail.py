"""Отправка писем по SMTP.

Адрес сервера задаётся в окружении (`MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`,
`MAIL_FROM`, `MAIL_SECURITY`). Если `MAIL_HOST` не задан, письмо только пишется в лог:
так удобно в разработке, код из письма виден в консоли сервера.

Ошибка отправки не должна ломать действие пользователя, поэтому `send` её только логирует.
"""

import asyncio
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Awaitable, Callable

from core.config import settings

log = logging.getLogger("mail")


@dataclass
class Mail:
    to: str
    subject: str
    text: str
    html: str | None = None


def _build(mail: Mail) -> EmailMessage:
    cfg = settings.mail
    message = EmailMessage()
    message["From"] = formataddr((cfg.from_name, cfg.from_address))
    message["To"] = mail.to
    message["Subject"] = mail.subject
    message.set_content(mail.text)
    if mail.html:
        message.add_alternative(mail.html, subtype="html")
    return message


def _send_smtp(message: EmailMessage) -> None:
    cfg = settings.mail
    context = ssl.create_default_context()
    if cfg.security == "ssl":
        client: smtplib.SMTP = smtplib.SMTP_SSL(cfg.host, cfg.port, context=context, timeout=15)
    else:
        client = smtplib.SMTP(cfg.host, cfg.port, timeout=15)
    with client:
        if cfg.security == "starttls":
            client.starttls(context=context)
        if cfg.username:
            client.login(cfg.username, cfg.password)
        client.send_message(message)


async def _deliver(mail: Mail) -> None:
    if not settings.mail.host:
        log.warning("Письмо (SMTP не настроен) для %s: %s\n%s", mail.to, mail.subject, mail.text)
        return
    await asyncio.to_thread(_send_smtp, _build(mail))


# Тесты подменяют отправителя, чтобы собирать письма в список.
sender: Callable[[Mail], Awaitable[None]] = _deliver


async def send(mail: Mail) -> None:
    try:
        await sender(mail)
    except Exception:  # noqa: BLE001 — любая ошибка сети или сервера не должна ронять запрос
        log.exception("Не удалось отправить письмо для %s: %s", mail.to, mail.subject)
