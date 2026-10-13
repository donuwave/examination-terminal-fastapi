from typing import Dict, List

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api_v1.auth.dependencies import get_user_id_in_access_token
from api_v1.notification import crud
from api_v1.notification.schemas import NotificationGet, PrefIn, UnreadCount
from core.models import db_helper

http_bearer = HTTPBearer()
router = APIRouter(tags=["Notification"], dependencies=[Depends(http_bearer)])


@router.get("/", response_model=List[NotificationGet])
async def get_notifications(
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Уведомления от новых к старым, постранично."""
    return await crud.list_notifications(session, user_id, limit, offset)


@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    return UnreadCount(count=await crud.unread_count(session, user_id))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def read_all(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    await crud.mark_all_read(session, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/settings", response_model=Dict[str, bool])
async def get_settings(
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    """Включён ли каждый тип уведомлений. По умолчанию включены все."""
    return await crud.get_prefs(session, user_id)


@router.put("/settings", response_model=Dict[str, bool])
async def put_setting(
    data: PrefIn,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    await crud.set_pref(session, user_id, data.kind, data.enabled)
    return await crud.get_prefs(session, user_id)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def read_one(
    notification_id: int,
    user_id: int = Depends(get_user_id_in_access_token),
    session: AsyncSession = Depends(db_helper.scoped_session_dependency),
):
    await crud.mark_read(session, user_id, notification_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
