from fastapi import APIRouter
from server.config import settings

router = APIRouter(prefix="/api/avatar", tags=["avatar"])


@router.get("/config")
async def get_avatar_config():
    return {
        "appId": settings.avatar_app_id,
        "appSecret": settings.avatar_app_secret,
        "gatewayServer": settings.avatar_gateway_server,
        "asrConfig": {},
    }
