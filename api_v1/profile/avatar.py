import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from core.config import BaseDir

UPLOAD_DIR = BaseDir / "uploads" / "avatars"
MAX_SIZE = 2 * 1024 * 1024

# Тип определяем по началу файла, а не по имени и заголовку, которые присылает клиент.
SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpg"),
)


def file_path(stored_name: str) -> Path:
    return UPLOAD_DIR / stored_name


def delete_file(stored_name: str | None) -> None:
    if stored_name:
        file_path(stored_name).unlink(missing_ok=True)


def _extension(head: bytes) -> str | None:
    for signature, extension in SIGNATURES:
        if head.startswith(signature):
            return extension
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


async def save_avatar(upload: UploadFile) -> str:
    """Сохраняет картинку под случайным именем и возвращает имя файла."""
    data = await upload.read(MAX_SIZE + 1)
    if len(data) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Картинка больше {MAX_SIZE // 1024 // 1024} МБ",
        )
    extension = _extension(data[:12])
    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Нужна картинка PNG, JPEG или WebP"
        )
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{extension}"
    file_path(name).write_bytes(data)
    return name
