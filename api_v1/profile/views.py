from typing import Union

from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_user_id_in_access_token
from api_v1.profile import avatar as avatar_storage
from api_v1.profile import crud as profile_crud
from api_v1.profile import public_crud
from api_v1.profile.public_schemas import PrivateProfile, ProfileCourses, PublicProfile
from api_v1.profile.schemas import ProfileGet, ProfileUpdate
from core.models import db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["Profile"], dependencies=[Depends(http_bearer)])


@router.get("/me", response_model=ProfileGet)
async def get_profile(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await profile_crud.get_profile(session=session, user_id=user_id)


@router.patch("/", response_model=ProfileGet)
async def update_profile(
    profile_update: ProfileUpdate,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return await profile_crud.update_profile(
        profile_update=profile_update, session=session, user_id=user_id
    )


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Удаляет аккаунт текущего пользователя."""
    await profile_crud.delete_account(session=session, user_id=user_id)


@router.post("/avatar", response_model=ProfileGet)
async def upload_avatar(
    file: UploadFile,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Заменяет аватар текущего пользователя."""
    return await profile_crud.set_avatar(session=session, user_id=user_id, upload=file)


@router.delete("/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def delete_avatar(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    await profile_crud.remove_avatar(session=session, user_id=user_id)


# Маршруты с числом в пути стоят после /me и /password, иначе они перехватят эти адреса.
@router.get("/{profile_id}", response_model=Union[PrivateProfile, PublicProfile])
async def get_other_profile(
    profile_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Профиль другого пользователя. Что видно, зависит от того, кто смотрит."""
    return await public_crud.get_profile_card(session, user_id, profile_id)


@router.get("/{profile_id}/courses", response_model=ProfileCourses)
async def get_other_profile_courses(
    profile_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Курсы преподавателя или студента с учётом прав смотрящего."""
    return await public_crud.get_profile_courses(session, user_id, profile_id, limit, offset)


@router.get("/{profile_id}/avatar")
async def get_avatar(
    profile_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Картинка профиля. Видна тем, кто вправе видеть сам профиль."""
    path = await public_crud.avatar_path(session, user_id, profile_id)
    return FileResponse(path, headers={"Cache-Control": "private, no-cache"})
