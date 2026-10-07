from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.course_material import storage
from api_v1.course_material.dependencies import (
    get_course_for_member,
    get_course_for_teacher,
)
from api_v1.course_material.schemas import MaterialGet
from core.models import Course, CourseMaterial, MaterialFile, db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["CourseMaterial"], dependencies=[Depends(http_bearer)])


@router.get("/{course_id}/materials", response_model=list[MaterialGet])
async def get_materials(
    course: Course = Depends(get_course_for_member),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    result = await session.scalars(
        select(CourseMaterial)
        .where(CourseMaterial.course_id == course.id)
        .order_by(CourseMaterial.id)
    )
    return list(result)


@router.post(
    "/{course_id}/materials",
    response_model=MaterialGet,
    status_code=status.HTTP_201_CREATED,
)
async def create_material(
    title: str = Form(min_length=1, max_length=200),
    description: str = Form(""),
    files: List[UploadFile] = File(default=[]),
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    files = [item for item in files if item.filename]
    if len(files) > storage.MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Можно прикрепить не больше {storage.MAX_FILES} файлов",
        )

    saved: list[MaterialFile] = []
    try:
        for upload in files:
            stored_name, size = await storage.save_upload(upload)
            saved.append(
                MaterialFile(
                    filename=upload.filename[:255],
                    stored_name=stored_name,
                    content_type=upload.content_type or "application/octet-stream",
                    size=size,
                )
            )

        material = CourseMaterial(
            course_id=course.id,
            title=title.strip(),
            description=description.strip(),
            files=saved,
        )
        session.add(material)
        await session.commit()
    except Exception:
        storage.delete_files([item.stored_name for item in saved])
        raise

    await session.refresh(material)
    return material


@router.delete(
    "/{course_id}/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_material(
    material_id: int,
    course: Course = Depends(get_course_for_teacher),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    material = await session.get(CourseMaterial, material_id)
    if material is None or material.course_id != course.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Материал не найден")

    stored_names = [item.stored_name for item in material.files]
    await session.delete(material)
    await session.commit()
    storage.delete_files(stored_names)


@router.get("/{course_id}/materials/files/{file_id}")
async def download_file(
    file_id: int,
    course: Course = Depends(get_course_for_member),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    item = await session.get(MaterialFile, file_id)
    material = await session.get(CourseMaterial, item.material_id) if item else None
    if item is None or material is None or material.course_id != course.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")

    path = storage.file_path(item.stored_name)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")

    return FileResponse(path, media_type=item.content_type, filename=item.filename)
