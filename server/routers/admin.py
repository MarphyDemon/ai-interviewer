import json
import time
import hashlib
import hmac
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlmodel import Session, select
from server.database import get_session
from server.models import LLMConfig, AvatarProviderConfig
from server.config import settings
from server.services.common import mask_api_key
from server.services.crypto_service import encrypt, decrypt

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _sign(payload: str) -> str:
    return hmac.new(
        settings.admin_password.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def _create_token() -> str:
    expiry = int(time.time()) + 86400
    payload = f"{expiry}"
    sig = _sign(payload)
    return f"{expiry}.{sig}"


def _verify_token(token: str) -> bool:
    parts = token.split(".")
    if len(parts) != 2:
        return False
    expiry_str, sig = parts
    try:
        expiry = int(expiry_str)
    except ValueError:
        return False
    if time.time() > expiry:
        return False
    expected_sig = _sign(expiry_str)
    return hmac.compare_digest(sig, expected_sig)


def verify_token(authorization: str | None = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    token = authorization.split(" ", 1)[1]
    if not _verify_token(token):
        raise HTTPException(401, "Invalid or expired token")
    return token


class VerifyRequest(BaseModel):
    password: str


class ConfigRequest(BaseModel):
    name: str
    baseUrl: str
    apiKey: str
    model: str


class UpdateConfigRequest(BaseModel):
    name: str | None = None
    baseUrl: str | None = None
    apiKey: str | None = None
    model: str | None = None


@router.post("/verify")
async def verify_admin(req: VerifyRequest):
    if req.password != settings.admin_password:
        raise HTTPException(403, "Wrong password")
    return {"token": _create_token()}


@router.get("/llm-config")
async def list_configs(
    session: Session = Depends(get_session),
    _: str = Depends(verify_token),
):
    configs = session.exec(select(LLMConfig)).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "baseUrl": c.base_url,
            "apiKeyMasked": mask_api_key(decrypt(c.api_key)),
            "model": c.model,
            "isActive": c.is_active,
        }
        for c in configs
    ]


@router.post("/llm-config")
async def create_config(
    req: ConfigRequest,
    session: Session = Depends(get_session),
    _: str = Depends(verify_token),
):
    cfg = LLMConfig(
        name=req.name,
        base_url=req.baseUrl,
        api_key=encrypt(req.apiKey),
        model=req.model,
    )
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return {"id": cfg.id, "name": cfg.name}


@router.put("/llm-config/{config_id}")
async def update_config(
    config_id: int,
    req: UpdateConfigRequest,
    session: Session = Depends(get_session),
    _: str = Depends(verify_token),
):
    cfg = session.get(LLMConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    if req.name is not None:
        cfg.name = req.name
    if req.baseUrl is not None:
        cfg.base_url = req.baseUrl
    if req.apiKey is not None:
        cfg.api_key = encrypt(req.apiKey)
    if req.model is not None:
        cfg.model = req.model
    session.add(cfg)
    session.commit()
    return {"ok": True}


@router.post("/llm-config/{config_id}/activate")
async def activate_config(
    config_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(verify_token),
):
    configs = session.exec(select(LLMConfig)).all()
    for c in configs:
        c.is_active = c.id == config_id
        session.add(c)
    session.commit()
    return {"ok": True}


# ---------- 数字人服务凭证（AvatarProviderConfig，镜像 LLMConfig 模式）----------


class AvatarConfigRequest(BaseModel):
    name: str
    appId: str
    appSecret: str
    gatewayServer: str


class UpdateAvatarConfigRequest(BaseModel):
    name: str | None = None
    appId: str | None = None
    appSecret: str | None = None
    gatewayServer: str | None = None


@router.get("/avatar-config")
async def list_avatar_configs(
    session: Session = Depends(get_session),
    _: str = Depends(verify_token),
):
    configs = session.exec(select(AvatarProviderConfig)).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "appId": c.app_id,
            "appSecretMasked": mask_api_key(decrypt(c.app_secret)),
            "gatewayServer": c.gateway_server,
            "isActive": c.is_active,
        }
        for c in configs
    ]


@router.post("/avatar-config")
async def create_avatar_config(
    req: AvatarConfigRequest,
    session: Session = Depends(get_session),
    _: str = Depends(verify_token),
):
    cfg = AvatarProviderConfig(
        name=req.name,
        app_id=req.appId,
        app_secret=encrypt(req.appSecret),
        gateway_server=req.gatewayServer,
    )
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return {"id": cfg.id, "name": cfg.name}


@router.put("/avatar-config/{config_id}")
async def update_avatar_config(
    config_id: int,
    req: UpdateAvatarConfigRequest,
    session: Session = Depends(get_session),
    _: str = Depends(verify_token),
):
    cfg = session.get(AvatarProviderConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    if req.name is not None:
        cfg.name = req.name
    if req.appId is not None:
        cfg.app_id = req.appId
    if req.appSecret is not None:
        cfg.app_secret = encrypt(req.appSecret)
    if req.gatewayServer is not None:
        cfg.gateway_server = req.gatewayServer
    session.add(cfg)
    session.commit()
    return {"ok": True}


@router.post("/avatar-config/{config_id}/activate")
async def activate_avatar_config(
    config_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(verify_token),
):
    configs = session.exec(select(AvatarProviderConfig)).all()
    for c in configs:
        c.is_active = c.id == config_id
        session.add(c)
    session.commit()
    return {"ok": True}


@router.delete("/avatar-config/{config_id}")
async def delete_avatar_config(
    config_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(verify_token),
):
    cfg = session.get(AvatarProviderConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    session.delete(cfg)
    session.commit()
    return {"ok": True}
