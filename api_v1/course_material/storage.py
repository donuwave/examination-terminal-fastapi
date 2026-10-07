import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from core.config import BaseDir

UPLOAD_DIR = BaseDir / "uploads" / "materials"
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_FILES = 5
CHUNK = 1024 * 256


def file_path(stored_name: str) -> Path:
    return UPLOAD_DIR / stored_name


def delete_files(stored_names: list[str]) -> None:
    for name in stored_names:
        file_path(name).unlink(missing_ok=True)


async def save_upload(upload: UploadFile) -> tuple[str, int]:
    """Сохраняет файл под случайным именем. Возвращает имя на диске и размер."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    stored_name = uuid.uuid4().hex
    size = 0
    path = file_path(stored_name)

    try:
        with path.open("wb") as out:
            while chunk := await upload.read(CHUNK):
                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Файл «{upload.filename}» больше {MAX_FILE_SIZE // 1024 // 1024} МБ",
                    )
                out.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise

    return stored_name, size
