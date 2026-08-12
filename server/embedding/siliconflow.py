import httpx
from server.config import settings


async def get_embedding(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.embedding_base_url}/embeddings",
            json={
                "model": settings.embedding_model,
                "input": text,
            },
            headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]
