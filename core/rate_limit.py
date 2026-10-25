"""Ограничение частоты запросов в памяти процесса.

Хватает для одного экземпляра приложения. Если приложение будет работать в нескольких
процессах, счётчики нужно вынести в общее хранилище, например в Redis.
"""

import time
from collections import defaultdict, deque

from fastapi import HTTPException, status


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int, message: str):
        self.limit = limit
        self.window = window_seconds
        self.message = message
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def _fresh(self, key: str) -> deque[float]:
        events = self._events[key]
        border = time.monotonic() - self.window
        while events and events[0] <= border:
            events.popleft()
        if not events:
            self._events.pop(key, None)
            return self._events[key]
        return events

    def check(self, key: str) -> None:
        """Бросает 429, если лимит исчерпан."""
        events = self._fresh(key)
        if len(events) >= self.limit:
            wait = max(1, int(events[0] + self.window - time.monotonic()))
            minutes = -(-wait // 60)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{self.message}. Попробуйте через {minutes} мин",
                headers={"Retry-After": str(wait)},
            )

    def hit(self, key: str) -> None:
        self._fresh(key).append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._events.clear()
        else:
            self._events.pop(key, None)


login_limiter = RateLimiter(5, 15 * 60, "Слишком много неудачных попыток входа")
registration_limiter = RateLimiter(10, 60 * 60, "Слишком много регистраций с вашего адреса")

password_limiter = RateLimiter(5, 15 * 60, "Слишком много неверных попыток смены пароля")

# Сброс пароля: по почте и по адресу запроса. Запросы считаются всегда, есть такая почта или нет.
reset_email_limiter = RateLimiter(3, 60 * 60, "Слишком много запросов кода для этой почты")
reset_ip_limiter = RateLimiter(10, 60 * 60, "Слишком много запросов кода с вашего адреса")
reset_check_limiter = RateLimiter(10, 15 * 60, "Слишком много неверных кодов")
