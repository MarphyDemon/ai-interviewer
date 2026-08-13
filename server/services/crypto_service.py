import base64
import hashlib
from cryptography.fernet import Fernet
from server.config import settings


def _get_key() -> bytes:
    """从 encryption_key 派生 32 字节 Fernet key"""
    raw = settings.encryption_key.encode()
    digest = hashlib.sha256(raw).digest()  # 固定 32 字节
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_get_key())


def encrypt(plaintext: str) -> str:
    """加密字符串，返回 base64 密文"""
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """解密 base64 密文，返回明文"""
    if not ciphertext:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        # 兼容旧数据：明文存储的 key 直接返回
        return ciphertext
