"""用户认证服务：pbkdf2 密码哈希 + HMAC token（携带 user_id）。

设计说明：
- 密码哈希用标准库 hashlib.pbkdf2_hmac，零依赖（与 Django 同方案）。
- token 复用 HMAC 签名模式（与 admin 一致），key 用 encryption_key 与 admin_password 隔离。
- token 格式：{user_id}.{expiry}.{sig}，无状态，7 天有效。
"""
import base64
import hashlib
import hmac
import secrets
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from server.config import settings
from server.database import get_session
from server.models import User


# ---------- 密码哈希 ----------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 100_000
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2$sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    parts = stored.split("$")
    if len(parts) != 5 or parts[0] != "pbkdf2":
        return False
    try:
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3])
        dk = base64.b64decode(parts[4])
    except Exception:
        return False
    return hmac.compare_digest(
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations),
        dk,
    )


# ---------- HMAC token ----------

def _sign(payload: str) -> str:
    return hmac.new(
        settings.encryption_key.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def create_user_token(user_id: int) -> str:
    expiry = int(time.time()) + 86400 * 7  # 7 天
    payload = f"{user_id}:{expiry}"
    sig = _sign(payload)
    return f"{user_id}.{expiry}.{sig}"


def verify_user_token(token: str) -> Optional[int]:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        user_id = int(parts[0])
        expiry = int(parts[1])
        sig = parts[2]
    except ValueError:
        return None
    if time.time() > expiry:
        return None
    payload = f"{user_id}:{expiry}"
    expected_sig = _sign(payload)
    if not hmac.compare_digest(sig, expected_sig):
        return None
    return user_id


# ---------- FastAPI 依赖 ----------

def get_current_user(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    token = authorization.split(" ", 1)[1]
    user_id = verify_user_token(token)
    if user_id is None:
        raise HTTPException(401, "登录已过期，请重新登录")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(401, "用户不存在")
    return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求当前用户为管理员角色。"""
    if current_user.role != "admin":
        raise HTTPException(403, "需要管理员权限")
    return current_user


def get_optional_user(
    authorization: Optional[str] = Header(None),
    session: Session = Depends(get_session),
) -> Optional[User]:
    """可选认证：有 token 则返回用户，无 token 返回 None。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    user_id = verify_user_token(token)
    if user_id is None:
        return None
    return session.get(User, user_id)
