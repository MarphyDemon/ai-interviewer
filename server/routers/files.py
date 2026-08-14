"""本地文件服务路由（仅 LocalStorage 模式下使用）。"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from server.services.storage_service import storage

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/{key:path}")
async def serve_file(key: str):
    """提供本地存储的文件下载。"""
    if not hasattr(storage, "_resolve"):
        # S3 模式，文件走 S3 直连
        raise HTTPException(404, "文件服务不可用")
    data = await storage.read(key)
    if data is None:
        raise HTTPException(404, "文件不存在")
    return Response(content=data)