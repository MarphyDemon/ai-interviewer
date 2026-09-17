"""内置示例 MCP server（stdio 传输，可独立运行）。

用途：在没有网络、没有第三方 MCP server 的环境下，验证本仓库 MCP 链路
（client → 单行 JSON-RPC → initialize → tools/list → tools/call）能端到端跑通，
并为「题库检索」「面试前了解目标公司」两个场景提供**离线、确定性**的数据源。

运行：
    python -m server.mcp_servers.sample_interview_server   # 推荐（与 mcp_service 默认配置一致）
    python server/mcp_servers/sample_interview_server.py

协议实现范围（对齐 MCP 2024-11-05）：
- initialize / notifications/initialized / ping
- tools/list / tools/call
- 未知方法 → -32601，非法参数或未知工具 → -32602，报文不可解析 → -32700

约束：
- 纯离线、确定性：不访问网络、不读写文件、不依赖数据库
- stdout 只输出协议帧（一行一个 JSON-RPC 消息），日志一律写 stderr
"""

import json
import re
import sys
from typing import Any, Optional

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "ai-interviewer-sample"
SERVER_VERSION = "0.1.0"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# ---------- 内置离线题库（示例数据，非真实企业题库） ----------

QUESTION_BANK: list[dict] = [
    {
        "id": "q_fe_001",
        "position": "前端",
        "difficulty": "中等",
        "question": "Vue 3 的响应式系统相比 Vue 2 有什么变化？实际项目里你怎么避免不必要的更新？",
        "reference_answer": (
            "Vue 3 用 Proxy 替代 defineProperty，原生支持数组变更与新增属性；"
            "减少更新的手段包括 shallowRef/shallowReactive、computed 缓存、v-memo、"
            "组件拆分与虚拟列表，并配合 Performance 面板定位重复渲染。"
        ),
        "tags": ["Vue", "响应式", "性能优化"],
    },
    {
        "id": "q_fe_002",
        "position": "前端",
        "difficulty": "简单",
        "question": "浏览器从输入 URL 到页面渲染完成，中间经历了哪些关键阶段？",
        "reference_answer": (
            "DNS 解析 → TCP/TLS 建连 → 发送 HTTP 请求 → 服务端响应 → 解析 HTML 构建 DOM → "
            "CSSOM → 渲染树 → 布局 → 绘制 → 合成；需说明阻塞资源与重排重绘的影响。"
        ),
        "tags": ["浏览器原理", "渲染流程"],
    },
    {
        "id": "q_fe_003",
        "position": "前端",
        "difficulty": "困难",
        "question": "首屏 5 秒的管理后台，你会按什么顺序排查并优化？",
        "reference_answer": (
            "先量化（Lighthouse / Performance）→ 查网络瀑布（分包、体积、CDN、HTTP 缓存）→ "
            "查主线程长任务与重复渲染 → 按收益排序逐项改造并回归对比。"
        ),
        "tags": ["性能优化", "方法论"],
    },
    {
        "id": "q_be_001",
        "position": "后端",
        "difficulty": "中等",
        "question": "缓存与数据库如何保持一致？请说明你采用的方案和它的失效边界。",
        "reference_answer": (
            "常见 Cache Aside（先更新库再删缓存）、延迟双删、订阅 binlog 等；"
            "必须说明不一致窗口的兜底：过期时间、重试、对账与补偿任务。"
        ),
        "tags": ["缓存", "一致性", "分布式"],
    },
    {
        "id": "q_be_002",
        "position": "后端",
        "difficulty": "中等",
        "question": "数据库索引失效的常见场景有哪些？你如何定位一条慢 SQL？",
        "reference_answer": (
            "隐式类型转换、函数包裹列、前导模糊匹配、不满足最左前缀、区分度过低等；"
            "先用慢查询日志定位，再看 EXPLAIN 的访问类型与扫描行数。"
        ),
        "tags": ["数据库", "索引", "SQL"],
    },
    {
        "id": "q_be_003",
        "position": "后端",
        "difficulty": "困难",
        "question": "服务如何做并发控制？谈谈你对锁与幂等的实践。",
        "reference_answer": (
            "乐观锁/悲观锁的选型、分布式锁的失效风险、唯一索引兜底、幂等键设计、"
            "以及超时与重试策略；需要给出并发量与失败率等量化结果。"
        ),
        "tags": ["并发", "锁", "幂等"],
    },
    {
        "id": "q_algo_001",
        "position": "算法",
        "difficulty": "中等",
        "question": "哈希表和平衡树的适用场景分别是什么？",
        "reference_answer": (
            "哈希表平均 O(1) 查找但不支持范围查询与有序遍历；平衡树 O(log n) 且支持有序/范围操作，"
            "内存开销更大，需结合查询模式与数据规模选择。"
        ),
        "tags": ["数据结构", "复杂度"],
    },
    {
        "id": "q_algo_002",
        "position": "算法",
        "difficulty": "困难",
        "question": "海量数据去重与 Top K 问题你会怎么设计？",
        "reference_answer": (
            "哈希分片 + 分治、Bitmap、布隆过滤器（可容忍误判）、小顶堆维护 Top K，"
            "必要时配合外部排序与流式处理，需说明内存与精度取舍。"
        ),
        "tags": ["系统设计", "大数据", "算法"],
    },
    {
        "id": "q_data_001",
        "position": "数据",
        "difficulty": "中等",
        "question": "数据倾斜是怎么产生的？你会如何排查和处理？",
        "reference_answer": (
            "key 分布不均、join 放大、空值集中等；可用加盐打散、map join、"
            "预聚合、调整并行度解决，并说明倾斜前后的任务耗时对比。"
        ),
        "tags": ["数据工程", "性能"],
    },
    {
        "id": "q_common_001",
        "position": "通用",
        "difficulty": "简单",
        "question": "请用两分钟做一个自我介绍，重点讲与岗位相关的经历。",
        "reference_answer": (
            "结构：我是谁 → 与岗位最相关的两件事（含量化结果）→ 为什么匹配这个岗位；"
            "控制时长并给面试官留下可追问的抓手。"
        ),
        "tags": ["自我介绍", "表达结构"],
    },
]

# ---------- 内置公司档案 stub（示例数据，非官方信息） ----------

COMPANY_PROFILES: dict[str, dict] = {
    "字节跳动": {
        "industry": "互联网 / 内容与短视频平台",
        "scale": "大型",
        "common_stack": ["Go", "Python", "Java", "React/Vue", "自研数据与推荐平台"],
        "interview_focus": [
            "算法与数据结构（现场编码占比较高）",
            "工程实践与性能优化（有量化指标更佳）",
            "业务理解与数据意识",
        ],
    },
    "阿里巴巴": {
        "industry": "互联网 / 电商与云计算",
        "scale": "大型",
        "common_stack": ["Java", "Go", "Python", "React/Vue", "云原生基础设施"],
        "interview_focus": [
            "分布式与高并发场景设计",
            "中间件与稳定性治理经验",
            "技术方案的取舍与成本意识",
        ],
    },
    "某初创 SaaS 公司": {
        "industry": "企业服务 / SaaS",
        "scale": "中小型",
        "common_stack": ["Python/Node.js", "Vue/React", "PostgreSQL", "云主机部署"],
        "interview_focus": [
            "全栈落地能力与交付速度",
            "在资源受限下的技术选型",
            "主动性与多角色协作",
        ],
    },
}

_PROFILE_DISCLAIMER = "（离线示例数据，非企业官方信息，仅用于演示面试准备流程）"

# ---------- 工具定义 ----------

TOOLS: list[dict] = [
    {
        "name": "search_question_bank",
        "description": (
            "在内置离线题库中按关键词检索面试题与参考答案。"
            "可用于校验候选人答案、挑选同知识点的追问题目。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词，如「Vue 响应式」「缓存一致性」「Top K」",
                },
                "position": {
                    "type": "string",
                    "description": "岗位方向过滤：前端/后端/算法/数据/通用，缺省不过滤",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "返回条数，缺省 3",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_company_profile",
        "description": (
            "获取目标公司的档案摘要（行业、规模、常见技术栈、面试关注点），"
            "用于面试前了解目标公司并生成针对性的提问角度。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "公司名称，如「字节跳动」",
                },
            },
            "required": ["company"],
        },
    },
]


# ---------- 工具实现 ----------


def _tokenize(text: str) -> list[str]:
    """把查询串切成英文词与中文词（2 字以上），用于确定性关键词打分。"""
    return re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,}|[\u4e00-\u9fa5]{2,}", text or "")


def search_question_bank(query: str, position: str, limit: int) -> str:
    terms = _tokenize(query)
    if not terms:
        return f"query=「{query}」未包含可检索的中文/英文关键词（至少 2 个字符），请换个说法。"

    scored: list[tuple[int, int, dict]] = []
    for idx, item in enumerate(QUESTION_BANK):
        if position and position != item["position"]:
            continue
        haystack = " ".join(
            [item["question"], item["reference_answer"], item["position"], " ".join(item["tags"])]
        )
        score = sum(haystack.count(term) for term in terms)
        if score > 0:
            scored.append((score, idx, item))

    if not scored:
        scope = f"position={position}" if position else "全岗位"
        return f"未命中题库（query=「{query}」，{scope}）。建议改用更具体的技术关键词，如 缓存、索引、Vue、Top K。"

    scored.sort(key=lambda row: (-row[0], row[1]))
    picked = scored[:limit]

    lines = [f"命中 {len(picked)} 条（query=「{query}」，position={position or '不限'}）："]
    for rank, (score, _idx, item) in enumerate(picked, start=1):
        lines.append(
            f"[{rank}] ({item['position']} / {item['difficulty']} / 相关度 {score}) {item['question']}"
        )
        lines.append(f"    参考答案：{item['reference_answer']}")
        lines.append(f"    标签：{'、'.join(item['tags'])}")
    return "\n".join(lines)


def get_company_profile(company: str) -> str:
    key = next((k for k in COMPANY_PROFILES if k in company or company in k), None)
    if key is None:
        available = "、".join(COMPANY_PROFILES)
        return (
            f"未找到「{company}」的离线档案。当前内置：{available}。"
            "接入真实企业信息 MCP server（如企业信息查询类服务）后可获得完整档案。"
        )

    profile = COMPANY_PROFILES[key]
    lines = [
        f"公司：{key}",
        f"行业：{profile['industry']}",
        f"规模：{profile['scale']}",
        f"常见技术栈：{'、'.join(profile['common_stack'])}",
        "面试关注点：",
    ]
    lines.extend(f"  - {point}" for point in profile["interview_focus"])
    lines.append(_PROFILE_DISCLAIMER)
    return "\n".join(lines)


def _call_tool(name: str, args: dict) -> str:
    """执行工具并返回文本；参数非法时抛 ValueError（由上层转成 -32602）。"""
    if name == "search_question_bank":
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("参数 query 必填，且必须是非空字符串")
        position = args.get("position", "")
        if position is None:
            position = ""
        if not isinstance(position, str):
            raise ValueError("参数 position 必须是字符串")
        limit = args.get("limit", 3)
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("参数 limit 必须是 1-5 的整数")
        if not 1 <= limit <= 5:
            raise ValueError("参数 limit 超出范围，取值 1-5")
        return search_question_bank(query.strip(), position.strip(), limit)

    if name == "get_company_profile":
        company = args.get("company")
        if not isinstance(company, str) or not company.strip():
            raise ValueError("参数 company 必填，且必须是非空字符串")
        return get_company_profile(company.strip())

    raise KeyError(name)


# ---------- JSON-RPC 处理 ----------


def _error(req_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _result(req_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _text_result(text: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _handle(message: dict) -> Optional[dict]:
    """处理单条消息。通知（无 id）返回 None，不产生响应。"""
    req_id = message.get("id")
    is_notification = req_id is None
    method = message.get("method")

    if message.get("jsonrpc") != "2.0" or not isinstance(method, str):
        if is_notification:
            return None
        return _error(req_id, INVALID_REQUEST, "非法请求：需要 jsonrpc=2.0 与字符串 method")

    if method == "initialize":
        params = message.get("params") or {}
        client_version = params.get("protocolVersion") if isinstance(params, dict) else None
        return _result(
            req_id,
            {
                "protocolVersion": client_version or PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": "内置离线示例 MCP server：题库检索与公司档案 stub，仅用于链路验证。",
            },
        )

    if method == "notifications/initialized":
        _log("客户端已完成初始化")
        return None

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, dict):
            return _error(req_id, INVALID_PARAMS, "参数必须是对象：{name, arguments}")
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return _error(req_id, INVALID_PARAMS, "缺少参数 name（工具名）")
        arguments = params.get("arguments")
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return _error(req_id, INVALID_PARAMS, "参数 arguments 必须是对象")
        try:
            text = _call_tool(name, arguments)
        except KeyError:
            return _error(req_id, INVALID_PARAMS, f"未知工具：{name}")
        except ValueError as e:
            return _error(req_id, INVALID_PARAMS, f"工具 {name} 参数非法：{e}")
        except Exception as e:  # 兜底：工具内部异常也算可读错误，不中断会话
            _log(f"工具 {name} 执行失败：{e}")
            return _result(req_id, _text_result(f"工具 {name} 执行失败：{e}", is_error=True))
        return _result(req_id, _text_result(text))

    if is_notification:
        _log(f"收到未实现的通知 {method}（忽略）")
        return None
    return _error(req_id, METHOD_NOT_FOUND, f"未实现的方法：{method}")


def _log(message: str) -> None:
    """日志一律写 stderr，stdout 只允许协议帧。"""
    print(f"[{SERVER_NAME}] {message}", file=sys.stderr, flush=True)


def main() -> int:
    # Windows 下管道默认可能是 GBK，显式固定 UTF-8，避免中文协议帧乱码
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception as e:
            _log(f"重设 {getattr(stream, 'name', stream)} 编码失败：{e}")

    _log(f"启动，协议版本 {PROTOCOL_VERSION}，工具 {[t['name'] for t in TOOLS]}")

    while True:
        try:
            line = sys.stdin.readline()
        except (KeyboardInterrupt, EOFError):
            break
        if not line:
            break
        text = line.strip()
        if not text:
            continue

        try:
            message = json.loads(text)
        except json.JSONDecodeError as e:
            _log(f"无法解析的报文：{e}")
            _write(_error(None, PARSE_ERROR, f"JSON 解析失败：{e}"))
            continue

        if not isinstance(message, dict):
            _write(_error(None, INVALID_REQUEST, "报文必须是 JSON 对象"))
            continue

        response = _handle(message)
        if response is not None:
            _write(response)

    _log("退出")
    return 0


def _write(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
