"""
知识库上传处理流程测试

测试内容：
1. Markdown 解析（frontmatter + 正文分离）
2. 分块逻辑（长文本正确拆分，每块 <= 500 字符）
3. 批量 embedding 调用（硅基流动 API）
4. ChromaDB 写入验证（向量数 = chunk 数）
5. 状态流转（processing -> ready/failed）
6. 搜索功能（写入后可检索）

运行方式：
    cd d:\ai项目\ai-Interviewer
    python -m pytest server/tests/test_knowledge_pipeline.py -v

    # 或直接运行（不依赖 pytest）
    python server/tests/test_knowledge_pipeline.py
"""

import asyncio
import os
import sys
import tempfile

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from server.parsers.markdown_parser import parse_markdown, chunk_markdown
from server.embedding.siliconflow import get_embeddings_batch, get_embedding


# ==================== 测试数据 ====================

SAMPLE_MD_WITH_FRONTMATTER = """---
title: React面试题
position: 前端
difficulty: 中级
tags: ["react", "hooks"]
---

## useState 的作用

useState 是 React 的基础 Hook，用于在函数组件中管理状态。

它返回一个数组，第一个元素是当前状态值，第二个元素是更新状态的函数。

## useEffect 的作用

useEffect 用于处理副作用，比如订阅、数据获取、手动 DOM 操作。

它接收两个参数：副作用函数和依赖数组。
"""

SAMPLE_MD_NO_FRONTMATTER = """这是一段没有 frontmatter 的纯文本。

### HTML 语义化

语义化是指根据内容的结构化选择合适的标签。

### CSS 盒模型

盒模型包括 content、padding、border、margin。
"""

LONG_TEXT_NO_HEADINGS = "\n".join(
    [f"这是第 {i} 行内容，用于测试长文本在没有标题的情况下是否能够正确分块。" for i in range(200)]
)


# ==================== 测试用例 ====================


def test_parse_markdown_with_frontmatter():
    """测试1: 解析带 frontmatter 的 markdown"""
    metadata, body = parse_markdown(SAMPLE_MD_WITH_FRONTMATTER)

    assert metadata.get("title") == "React面试题"
    assert metadata.get("position") == "前端"
    assert metadata.get("difficulty") == "中级"
    assert "react" in metadata.get("tags", [])
    assert "useState 的作用" in body
    print("[PASS] test_parse_markdown_with_frontmatter")


def test_parse_markdown_without_frontmatter():
    """测试2: 解析不带 frontmatter 的 markdown"""
    metadata, body = parse_markdown(SAMPLE_MD_NO_FRONTMATTER)

    assert metadata == {}
    assert "HTML 语义化" in body
    assert "CSS 盒模型" in body
    print("[PASS] test_parse_markdown_without_frontmatter")


def test_chunk_markdown_basic():
    """测试3: 基本分块逻辑"""
    chunks = chunk_markdown(SAMPLE_MD_WITH_FRONTMATTER)

    assert len(chunks) > 0, "应该至少有一个 chunk"
    for chunk in chunks:
        assert "content" in chunk
        assert "title" in chunk
        assert "level" in chunk
        assert len(chunk["content"]) <= 500, f"chunk 过长: {len(chunk['content'])} 字符"
    print(f"[PASS] test_chunk_markdown_basic (共 {len(chunks)} 个 chunks)")


def test_chunk_markdown_long_text_no_headings():
    """测试4: 长文本无标题的分块（关键场景）"""
    chunks = chunk_markdown(LONG_TEXT_NO_HEADINGS)

    assert len(chunks) > 1, "长文本应该被拆分成多个 chunk"
    for i, chunk in enumerate(chunks):
        assert len(chunk["content"]) <= 500, f"chunk {i} 过长: {len(chunk['content'])} 字符"
    total_chars = sum(len(c["content"]) for c in chunks)
    print(f"[PASS] test_chunk_markdown_long_text_no_headings (共 {len(chunks)} 个 chunks, 总 {total_chars} 字符)")


def test_chunk_markdown_empty():
    """测试5: 空内容分块"""
    chunks = chunk_markdown("")
    assert chunks == [], "空内容应返回空列表"
    print("[PASS] test_chunk_markdown_empty")


def test_get_embedding_single():
    """测试6: 单条 embedding 调用"""
    emb = asyncio.run(get_embedding("测试文本"))

    assert isinstance(emb, list), "embedding 应该是 list"
    assert len(emb) > 0, "embedding 不应为空"
    assert all(isinstance(x, float) for x in emb), "embedding 元素应为 float"
    print(f"[PASS] test_get_embedding_single (维度: {len(emb)})")


def test_get_embeddings_batch():
    """测试7: 批量 embedding 调用"""
    texts = ["React是什么", "Vue是什么", "Angular是什么"]
    embeddings = asyncio.run(get_embeddings_batch(texts))

    assert len(embeddings) == 3, f"应返回 3 个 embedding，实际 {len(embeddings)}"
    for emb in embeddings:
        assert len(emb) > 0, "embedding 不应为空"
    print(f"[PASS] test_get_embeddings_batch (3 条, 每条维度 {len(embeddings[0])})")


def test_get_embeddings_batch_large():
    """测试8: 超过 batch_size 的批量调用（自动分批）"""
    texts = [f"测试文本 {i}" for i in range(40)]  # 超过单批 32 条
    embeddings = asyncio.run(get_embeddings_batch(texts))

    assert len(embeddings) == 40, f"应返回 40 个 embedding，实际 {len(embeddings)}"
    print(f"[PASS] test_get_embeddings_batch_large (40 条, 自动分 2 批)")


def test_chromadb_write_and_search():
    """测试9: ChromaDB 写入 + 搜索验证"""
    import chromadb
    from server.services.rag_service import add_chunks, search, delete_doc_chunks, get_knowledge_collection

    # 使用临时 doc_id 避免冲突
    test_doc_id = 99999

    # 准备测试数据
    chunks = [
        {
            "content": "useState 是 React Hook，用于管理组件状态",
            "title": "React Hooks",
            "position": "前端",
            "difficulty": "中级",
            "tags": '["react"]',
        },
        {
            "content": "useEffect 用于处理副作用，如数据获取和订阅",
            "title": "React Hooks",
            "position": "前端",
            "difficulty": "中级",
            "tags": '["react"]',
        },
    ]
    texts = [c["content"] for c in chunks]
    embeddings = asyncio.run(get_embeddings_batch(texts))

    # 写入
    add_chunks(doc_id=test_doc_id, chunks=chunks, embeddings=embeddings)

    # 验证写入
    collection = get_knowledge_collection()
    results = collection.get(where={"doc_id": test_doc_id})
    assert len(results["ids"]) == 2, f"应写入 2 条，实际 {len(results['ids'])}"

    # 搜索
    query_emb = asyncio.run(get_embedding("React 状态管理"))
    search_results = search(query_emb, top_k=2, where={"doc_id": test_doc_id})
    assert len(search_results) > 0, "搜索应返回结果"
    assert "useState" in search_results[0]["content"], "搜索结果应包含相关内容"

    # 清理
    delete_doc_chunks(test_doc_id)
    results_after = collection.get(where={"doc_id": test_doc_id})
    assert len(results_after["ids"]) == 0, "清理后应为空"

    print(f"[PASS] test_chromadb_write_and_search (写入2条, 搜索命中, 清理完成)")


def test_full_pipeline_simulation():
    """测试10: 完整流程模拟（解析 -> 分块 -> embedding -> 写入 -> 搜索 -> 删除）"""
    import chromadb
    from server.services.rag_service import add_chunks, search, delete_doc_chunks, get_knowledge_collection

    test_doc_id = 88888

    # 1. 解析
    metadata, body = parse_markdown(SAMPLE_MD_WITH_FRONTMATTER)
    assert metadata["title"] == "React面试题"

    # 2. 分块
    chunks_raw = chunk_markdown(body)
    assert len(chunks_raw) > 0

    # 3. 构造 chunk 数据
    chunks = [
        {
            "content": c["content"],
            "title": c["title"],
            "position": metadata.get("position", ""),
            "difficulty": metadata.get("difficulty", ""),
            "tags": str(metadata.get("tags", [])),
        }
        for c in chunks_raw
    ]

    # 4. 批量 embedding
    texts = [c["content"] for c in chunks]
    embeddings = asyncio.run(get_embeddings_batch(texts))
    assert len(embeddings) == len(chunks)

    # 5. 写入 ChromaDB
    add_chunks(doc_id=test_doc_id, chunks=chunks, embeddings=embeddings)

    # 6. 验证写入
    collection = get_knowledge_collection()
    stored = collection.get(where={"doc_id": test_doc_id})
    assert len(stored["ids"]) == len(chunks), f"写入数 {len(stored['ids'])} != chunk 数 {len(chunks)}"

    # 7. 搜索验证
    query_emb = asyncio.run(get_embedding("React hooks 有哪些"))
    results = search(query_emb, top_k=3, where={"doc_id": test_doc_id})
    assert len(results) > 0, "搜索应返回结果"

    # 8. 清理
    delete_doc_chunks(test_doc_id)

    print(f"[PASS] test_full_pipeline_simulation (解析->分块{len(chunks)}条->embedding->写入->搜索->清理)")


# ==================== 运行入口 ====================


def run_all():
    """运行所有测试（不依赖 pytest）"""
    tests = [
        test_parse_markdown_with_frontmatter,
        test_parse_markdown_without_frontmatter,
        test_chunk_markdown_basic,
        test_chunk_markdown_long_text_no_headings,
        test_chunk_markdown_empty,
        test_get_embedding_single,
        test_get_embeddings_batch,
        test_get_embeddings_batch_large,
        test_chromadb_write_and_search,
        test_full_pipeline_simulation,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {test.__name__}: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 个测试")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
