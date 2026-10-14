"""Выгрузка в CSV для Excel: UTF-8 с BOM и разделитель «;»."""

import csv
import io
from datetime import datetime
from typing import Iterable, Sequence
from urllib.parse import quote

from fastapi import Response

DANGEROUS_START = ("=", "+", "-", "@", "\t", "\r")


def safe(value: object) -> str:
    """Ячейка, начинающаяся со знака формулы, в Excel выполнилась бы как формула.
    Имена и почта задаются пользователями, поэтому такие значения экранируем апострофом."""
    text = "" if value is None else str(value)
    return "'" + text if text.startswith(DANGEROUS_START) else text


def when(seconds: int | None) -> str:
    return datetime.fromtimestamp(seconds).strftime("%d.%m.%Y %H:%M") if seconds else ""


def csv_response(filename: str, header: Sequence[str], rows: Iterable[Sequence[object]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe(cell) for cell in row])
    body = "﻿" + buffer.getvalue()
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
