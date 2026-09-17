import time
import hashlib
import hmac
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlmodel import Session, select
from server.database import get_session
from server.models import LLMConfig, AvatarProviderConfig, User, UserQuota, KnowledgeDoc, KnowledgeVersion, InviteCode
from server.config import settings
from server.services.common import mask_api_key
from server.services.crypto_service import encrypt, decrypt
from server.services.auth_service import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------- 旧 admin_token 机制（用于引导） ----------

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


# ---------- 混合认证：支持旧 admin_token 或新 role-based ----------

def require_admin_access(authorization: str | None = Header(None)):
    """管理员认证：支持旧 admin_token（引导用）或用户 role=admin。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未认证")
    token = authorization.split(" ", 1)[1]

    # 尝试旧 admin_token
    if _verify_token(token):
        return token

    # 尝试用户 role-based
    from server.services.auth_service import verify_user_token
    user_id = verify_user_token(token)
    if user_id is None:
        raise HTTPException(401, "登录已过期")
    from server.database import engine
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(401, "用户不存在")
        if user.role != "admin":
            raise HTTPException(403, "需要管理员权限")
    return token


# ---------- 请求/响应模型 ----------

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


class AvatarConfigRequest(BaseModel):
    name: str
    appId: str
    appSecret: str
    gatewayServer: str
    avatarImage: str = ""


class UpdateAvatarConfigRequest(BaseModel):
    name: str | None = None
    appId: str | None = None
    appSecret: str | None = None
    gatewayServer: str | None = None
    avatarImage: str | None = None


class PromoteRequest(BaseModel):
    role: str = "admin"


# ---------- 引导：admin_password 验证 ----------

@router.post("/verify")
async def verify_admin(req: VerifyRequest):
    if req.password != settings.admin_password:
        raise HTTPException(403, "Wrong password")
    return {"token": _create_token()}


# ---------- LLM 配置管理 ----------

@router.get("/llm-config")
async def list_configs(
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
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
    _: str = Depends(require_admin_access),
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
    _: str = Depends(require_admin_access),
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
    _: str = Depends(require_admin_access),
):
    configs = session.exec(select(LLMConfig)).all()
    for c in configs:
        c.is_active = c.id == config_id
        session.add(c)
    session.commit()
    return {"ok": True}


@router.post("/llm-config/{config_id}/deactivate")
async def deactivate_config(
    config_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    cfg = session.get(LLMConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    cfg.is_active = False
    session.add(cfg)
    session.commit()
    return {"ok": True}


@router.delete("/llm-config/{config_id}")
async def delete_config(
    config_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    cfg = session.get(LLMConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    session.delete(cfg)
    session.commit()
    return {"ok": True}


# ---------- 具身交互智能体服务凭证 ----------

@router.get("/avatar-config")
async def list_avatar_configs(
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    configs = session.exec(select(AvatarProviderConfig)).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "appId": c.app_id,
            "appSecretMasked": mask_api_key(decrypt(c.app_secret)),
            "gatewayServer": c.gateway_server,
            "avatarImage": c.avatar_image,
            "isActive": c.is_active,
        }
        for c in configs
    ]


@router.post("/avatar-config")
async def create_avatar_config(
    req: AvatarConfigRequest,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    cfg = AvatarProviderConfig(
        name=req.name,
        app_id=req.appId,
        app_secret=encrypt(req.appSecret),
        gateway_server=req.gatewayServer,
        avatar_image=req.avatarImage,
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
    _: str = Depends(require_admin_access),
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
    if req.avatarImage is not None:
        cfg.avatar_image = req.avatarImage
    session.add(cfg)
    session.commit()
    return {"ok": True}


@router.post("/avatar-config/{config_id}/activate")
async def activate_avatar_config(
    config_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    cfg = session.get(AvatarProviderConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    cfg.is_active = True
    session.add(cfg)
    session.commit()
    return {"ok": True}


@router.post("/avatar-config/{config_id}/deactivate")
async def deactivate_avatar_config(
    config_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    cfg = session.get(AvatarProviderConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    cfg.is_active = False
    session.add(cfg)
    session.commit()
    return {"ok": True}


@router.delete("/avatar-config/{config_id}")
async def delete_avatar_config(
    config_id: int,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    cfg = session.get(AvatarProviderConfig, config_id)
    if not cfg:
        raise HTTPException(404, "Config not found")
    session.delete(cfg)
    session.commit()
    return {"ok": True}


# ---------- 用户管理（P2 新增） ----------

@router.get("/users")
async def list_users(
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    users = session.exec(select(User)).all()
    results = []
    for u in users:
        quota = session.exec(select(UserQuota).where(UserQuota.user_id == u.id)).first()
        results.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "createdAt": u.created_at.isoformat() if u.created_at else None,
            "plan": quota.plan if quota else "free",
        })
    return results


@router.post("/users/{user_id}/promote")
async def promote_user(
    user_id: int,
    req: PromoteRequest,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    if req.role not in ("user", "admin"):
        raise HTTPException(400, "无效的角色")
    user.role = req.role
    session.add(user)
    session.commit()
    return {"ok": True, "role": user.role}


@router.post("/users/{user_id}/quota")
async def set_user_quota(
    user_id: int,
    req: dict,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    quota = session.exec(select(UserQuota).where(UserQuota.user_id == user_id)).first()
    if not quota:
        quota = UserQuota(user_id=user_id)
        session.add(quota)
    if "plan" in req:
        quota.plan = req["plan"]
    if "interviewLimit" in req:
        quota.interview_limit = req["interviewLimit"]
    if "knowledgeLimit" in req:
        quota.knowledge_limit = req["knowledgeLimit"]
    if "aiCallsLimit" in req:
        quota.ai_calls_limit = req["aiCallsLimit"]
    session.add(quota)
    session.commit()
    return {"ok": True}


# ---------- 平台统计看板（P4 新增） ----------

@router.get("/stats")
async def get_platform_stats(
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    from server.models import Interview, Report
    total_users = session.exec(select(User)).all()
    total_interviews = session.exec(select(Interview)).all()
    total_reports = session.exec(select(Report)).all()
    total_docs = session.exec(select(KnowledgeDoc)).all()
    total_versions = session.exec(select(KnowledgeVersion)).all()

    return {
        "totalUsers": len(total_users),
        "totalAdmins": sum(1 for u in total_users if u.role == "admin"),
        "totalInterviews": len(total_interviews),
        "totalReports": len(total_reports),
        "totalKnowledgeDocs": len(total_docs),
        "totalKnowledgeVersions": len(total_versions),
        "freePlanUsers": sum(1 for q in session.exec(select(UserQuota)).all() if q.plan == "free"),
        "standardPlanUsers": sum(1 for q in session.exec(select(UserQuota)).all() if q.plan == "standard"),
        "enterprisePlanUsers": sum(1 for q in session.exec(select(UserQuota)).all() if q.plan == "enterprise"),
    }


# ---- 邀请码管理 ----

class InviteCodeCreate(BaseModel):
    plan: str = "standard"
    max_uses: int = 10
    note: str | None = None


@router.get("/invite-codes")
async def list_invite_codes(
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    codes = session.exec(select(InviteCode).order_by(InviteCode.created_at.desc())).all()
    return [
        {
            "id": c.id,
            "code": c.code,
            "plan": c.plan,
            "maxUses": c.max_uses,
            "usedCount": c.used_count,
            "isActive": c.is_active,
            "expiresAt": c.expires_at.isoformat() if c.expires_at else None,
            "note": c.note,
            "createdAt": c.created_at.isoformat() if c.created_at else None,
        }
        for c in codes
    ]


@router.post("/invite-codes")
async def create_invite_code(
    req: InviteCodeCreate,
    session: Session = Depends(get_session),
    _: str = Depends(require_admin_access),
):
    import secrets
    code = secrets.token_urlsafe(12).upper()
    expires_at = datetime.utcnow() + __import__('datetime').timedelta(days=365)
    invite = InviteCode(
        code=code,
        plan=req.plan,
        max_uses=req.max_uses,
        used_count=0,
        is_active=True,
        expires_at=expires_at,
        note=req.note,
    )
    session.add(invite)
    session.commit()
    session.refresh(invite)
    return {"id": invite.id, "code": code}


@router.post("/invite-codes/{code}/redeem")
async def redeem_invite_code(
    code: str,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    invite = session.exec(select(InviteCode).where(InviteCode.code == code.upper())).first()
    if not invite or not invite.is_active:
        raise HTTPException(400, "邀请码无效或已失效")
    if invite.expires_at and invite.expires_at < datetime.utcnow():
        raise HTTPException(400, "邀请码已过期")
    if invite.used_count >= invite.max_uses:
        raise HTTPException(400, "邀请码已用完")

    invite.used_count += 1
    if invite.used_count >= invite.max_uses:
        invite.is_active = False

    quota = session.exec(select(UserQuota).where(UserQuota.user_id == user.id)).first()
    if not quota:
        quota = UserQuota(user_id=user.id, plan=invite.plan)
        session.add(quota)
    else:
        quota.plan = invite.plan

    session.add(invite)
    session.add(quota)
    session.commit()
    return {"ok": True, "plan": invite.plan}