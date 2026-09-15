"""面试事件总线：把 brain 流水线中的结构化事件旁路推送给前端。

设计背景：
具身交互智能体 SDK 的 BrainClient 只消费 SSE 的 `delta.content`，结构化事件（工具调用、
Widget 载荷、情绪决策、时延埋点）不能塞进正文字段，否则会污染播报文本。
因此用一条独立的 SSE 通道（GET /api/interview/{id}/events）旁路推送。

同一场面试可能有多个订阅者（多标签页、重连等），用 set[Queue] 支持一对多；
队列满时丢弃最旧事件，避免阻塞生成。
"""
import asyncio
from typing import Optional


_MAX_QUEUE = 256

_channels: dict[int, set[asyncio.Queue]] = {}


def publish(interview_id: int, event: dict) -> None:
    """向某场面试的所有订阅者广播事件（非阻塞）。

    在异步上下文中调用；若队列已满则丢弃最旧的一条再入队，
    以"丢旧事件"换取"不阻塞 LLM 生成"。
    """
    queues = _channels.get(interview_id)
    if not queues:
        return
    for q in list(queues):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            try:
                q.get_nowait()
                q.put_nowait(event)
            except Exception:
                pass


class Subscription:
    """一次事件订阅。

    刻意**不用 async generator** 实现：SSE 端点需要周期性地做 keep-alive 超时，
    若对 `agen.__anext__()` 施加超时，超时的取消异常会进入生成器内部，
    使生成器提前结束或与后续 `aclose()` 冲突（RuntimeError: already running）。
    这里改为直接持有队列，配合 `get(timeout)` 暴露超时语义，调用方无需处理生成器生命周期。
    """

    def __init__(self, interview_id: int) -> None:
        self._interview_id = interview_id
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE)
        self._closed = False
        _channels.setdefault(interview_id, set()).add(self._queue)

    async def get(self, timeout: float = 20.0) -> Optional[dict]:
        """取一条事件；超时返回 None，调用方据此发送心跳。"""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout)
        except asyncio.TimeoutError:
            return None

    def close(self) -> None:
        """注销订阅（同步、幂等）。"""
        if self._closed:
            return
        self._closed = True
        bucket = _channels.get(self._interview_id)
        if bucket is not None:
            bucket.discard(self._queue)
            if not bucket:
                _channels.pop(self._interview_id, None)


def subscribe(interview_id: int) -> Subscription:
    """创建订阅。"""
    return Subscription(interview_id)


def subscriber_count(interview_id: int) -> int:
    """当前订阅者数量（调试/健康检查用）。"""
    return len(_channels.get(interview_id, ()))
