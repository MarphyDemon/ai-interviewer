import json
import time
import hashlib
import hmac
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlmodel import Session, select
from server.database import get_session
from server.models import LLMConfig
from server.config import settings
from server.services.common import mask_api_key

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
            "apiKeyMasked": mask_api_key(c.api_key),
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
        api_key=req.apiKey,
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
        cfg.api_key = req.apiKey
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
