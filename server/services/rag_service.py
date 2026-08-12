import chromadb
from server.config import settings
from typing import List, Dict

_client = None


def get_chroma_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=str(settings.chroma_dir))
    return _client


def get_knowledge_collection():
    client = get_chroma_client()
    return client.get_or_create_collection("knowledge_chunks")


def add_chunks(doc_id: int, chunks: List[Dict], embeddings: List[List[float]]):
    collection = get_knowledge_collection()
    ids = [f"doc{doc_id}_chunk{i}" for i in range(len(chunks))]
    documents = [c["content"] for c in chunks]
    metadatas = [
        {
            "doc_id": doc_id,
            "position": c.get("position", ""),
            "difficulty": c.get("difficulty", ""),
            "tags": c.get("tags", ""),
            "chunk_index": i,
            "title": c.get("title", ""),
        }
        for i, c in enumerate(chunks)
    ]
    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def delete_doc_chunks(doc_id: int):
    collection = get_knowledge_collection()
    results = collection.get(where={"doc_id": doc_id})
    if results["ids"]:
        collection.delete(ids=results["ids"])


def search(query_embedding: list[float], top_k: int = 5, where: dict = None) -> List[Dict]:
    collection = get_knowledge_collection()
    kwargs = {"query_embeddings": [query_embedding], "n_results": top_k}
    if where:
        kwargs["where"] = where
    results = collection.query(**kwargs)
    docs = []
    for i in range(len(results["ids"][0])):
        docs.append({
            "id": results["ids"][0][i],
            "content": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i],
        })
    return docs
