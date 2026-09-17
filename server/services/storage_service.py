"""文件存储抽象层：支持本地文件系统与 S3 兼容对象存储。

用法：
  from server.services.storage_service import storage
  
  # 写入文件
  url = await storage.save("resumes/abc.pdf", data, content_type="application/pdf")
  
  # 读取文件
  data = await storage.read("resumes/abc.pdf")
  
  # 删除文件
  await storage.delete("resumes/abc.pdf")
"""
from pathlib import Path
from typing import Optional

from server.config import settings


class FileStorage:
    """文件存储基类。"""

    async def save(self, key: str, data: bytes, content_type: str = "") -> str:
        """保存文件，返回可访问的 URL。"""
        raise NotImplementedError

    async def read(self, key: str) -> Optional[bytes]:
        """读取文件内容。"""
        raise NotImplementedError

    async def delete(self, key: str) -> None:
        """删除文件。"""
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        """检查文件是否存在。"""
        raise NotImplementedError

    def get_url(self, key: str) -> str:
        """获取文件访问 URL。"""
        raise NotImplementedError


class LocalStorage(FileStorage):
    """本地文件系统存储。"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def _resolve(self, key: str) -> Path:
        # 防止路径穿越
        safe = Path(key).as_posix().lstrip("/")
        path = (self.base_dir / safe).resolve()
        if not str(path).startswith(str(self.base_dir.resolve())):
            raise ValueError(f"非法路径: {key}")
        return path

    async def save(self, key: str, data: bytes, content_type: str = "") -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return self.get_url(key)

    async def read(self, key: str) -> Optional[bytes]:
        path = self._resolve(key)
        if not path.exists():
            return None
        with open(path, "rb") as f:
            return f.read()

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def get_url(self, key: str) -> str:
        return f"/api/files/{key}"


class S3Storage(FileStorage):
    """S3 兼容对象存储。"""

    def __init__(self):
        import boto3

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        self.bucket = settings.s3_bucket

    async def save(self, key: str, data: bytes, content_type: str = "") -> str:
        kwargs = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": data,
        }
        if content_type:
            kwargs["ContentType"] = content_type
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: self.client.put_object(**kwargs))
        return self.get_url(key)

    async def read(self, key: str) -> Optional[bytes]:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None, lambda: self.client.get_object(Bucket=self.bucket, Key=key)
            )
            return resp["Body"].read()
        except self.client.exceptions.NoSuchKey:
            return None

    async def delete(self, key: str) -> None:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, lambda: self.client.delete_object(Bucket=self.bucket, Key=key)
        )

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False

    def get_url(self, key: str) -> str:
        # 如果配置了 S3 公网端点，返回直接 URL
        if settings.s3_endpoint:
            return f"{settings.s3_endpoint}/{self.bucket}/{key}"
        return f"/api/files/{key}"


# 全局单例：根据配置自动选择存储后端
def _create_storage() -> FileStorage:
    if settings.s3_endpoint and settings.s3_access_key:
        return S3Storage()
    return LocalStorage(settings.data_dir)


storage = _create_storage()