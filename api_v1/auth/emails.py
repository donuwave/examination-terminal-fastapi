"""Тексты писем, связанных с входом. Русский язык, текстовая и HTML-версии."""

from html import escape

from core.mail import Mail


def _wrap(title: str, body_html: str) -> str:
    return (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:480px;'
        'margin:0 auto;padding:24px;color:#1F2430">'
        f'<h2 style="margin:0 0 16px">{escape(title)}</h2>{body_html}'
        '<p style="margin-top:32px;font-size:12px;color:#6B7280">'
        "Это автоматическое письмо, отвечать на него не нужно.</p></div>"
    )


def reset_code_mail(to: str, code: str, minutes: int) -> Mail:
    text = (
        f"Код для сброса пароля: {code}\n\n"
        f"Он действует {minutes} минут. Если вы не просили сбросить пароль, просто проигнорируйте письмо: "
        "ваш пароль не изменится."
    )
    html = _wrap(
        "Сброс пароля",
        '<p>Код для сброса пароля:</p>'
        f'<p style="font-size:32px;font-weight:800;letter-spacing:6px;margin:12px 0">{escape(code)}</p>'
        f"<p>Он действует {minutes} минут. Если вы не просили сбросить пароль, "
        "просто проигнорируйте письмо: ваш пароль не изменится.</p>",
    )
    return Mail(to=to, subject=f"Код для сброса пароля: {code}", text=text, html=html)


def password_changed_mail(to: str) -> Mail:
    text = (
        "Пароль от вашего аккаунта был изменён.\n\n"
        "Если это сделали не вы, срочно сбросьте пароль ещё раз и напишите в поддержку."
    )
    html = _wrap(
        "Пароль изменён",
        "<p>Пароль от вашего аккаунта был изменён.</p>"
        "<p>Если это сделали не вы, срочно сбросьте пароль ещё раз и напишите в поддержку.</p>",
    )
    return Mail(to=to, subject="Пароль от аккаунта изменён", text=text, html=html)
