import os
import ssl
import asyncio
import httpx
import certifi
from server.config import settings

# 修复: 清除无效的 SSL_CERT_FILE 环境变量
_cert_file = os.environ.get("SSL_CERT_FILE", "")
if _cert_file and not os.path.exists(_cert_file):
    del os.environ["SSL_CERT_FILE"]

# 复用 SSL context 和 httpx client
_ctx = ssl.create_default_context(cafile=certifi.where())


async def get_embeddings_batch(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """批量获取 embedding，硅基流动单次最多 32 条"""
    results: list[list[float]] = []
    async with httpx.AsyncClient(timeout=60, verify=_ctx) as client:
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await client.post(
                f"{settings.embedding_base_url}/embeddings",
                json={
                    "model": settings.embedding_model,
                    "input": batch,
                },
                headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
            )
            if resp.status_code != 200:
                print(f"[Embedding] API returned {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()
            data = resp.json()
            # API 返回按 index 排序
            results.extend([d["embedding"] for d in data["data"]])
    return results


async def get_embedding(text: str) -> list[float]:
    return (await get_embeddings_batch([text]))[0]
