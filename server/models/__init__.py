from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    anonymous_uuid: str = Field(unique=True, index=True)
    username: Optional[str] = Field(default=None, unique=True, index=True)
    password_hash: Optional[str] = None
    preferred_avatar_config_id: Optional[int] = Field(default=None, foreign_key="avatarproviderconfig.id")
    role: str = "user"
    preferred_position: str = ""
    language: str = "zh"
    theme: str = "light"
    notification_settings: str = "{}"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeDoc(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    # 企业知识库：由组织成员上传时归属到组织，全组织共享；个人文档恒为 NULL
    org_id: Optional[int] = Field(default=None, foreign_key="organization.id", index=True)
    filename: str
    title: str = ""
    position: str = ""
    difficulty: str = ""
    tags: str = "[]"
    content: str = ""
    status: str = "processing"
    is_public: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Resume(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    filename: str
    file_path: str
    parsed_text: str = ""
    analysis_result: str = "{}"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JobDescription(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    # 企业岗位 JD：由组织成员创建时归属到组织，全组织共享；个人练习的 JD 恒为 NULL
    org_id: Optional[int] = Field(default=None, foreign_key="organization.id", index=True)
    title: str
    content: str = ""
    position: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Interview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    resume_id: Optional[int] = Field(default=None, foreign_key="resume.id")
    jd_id: Optional[int] = Field(default=None, foreign_key="jobdescription.id")
    # 企业筛选：由候选人邀请创建的面试会带上组织，个人练习恒为 NULL。
    # 组织成员据此获得该场面试报告的只读权限（见 org_service.can_view_interview）。
    org_id: Optional[int] = Field(default=None, foreign_key="organization.id", index=True)
    position: str
    difficulty: str
    duration: int = 30
    style: str = "温和"
    # 本次面试的考察重点（由 HR 在创建邀请时指定，注入面试 prompt）
    focus: str = ""
    status: str = "进行中"
    # 面试流程状态机阶段（见 server/services/interview_stage.py）
    stage: str = "opening"
    stage_updated_at: Optional[datetime] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None


class InterviewMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    interview_id: int = Field(foreign_key="interview.id")
    role: str
    content: str
    question_index: int = 0
    followup_level: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    interview_id: int = Field(foreign_key="interview.id", unique=True)
    total_score: float = 0
    dimension_scores: str = "[]"
    summary: str = ""
    per_question_reviews: str = "[]"
    resume_review: str = "{}"
    job_fit: str = ""
    match_score: Optional[float] = Field(default=None)
    match_breakdown: str = "[]"
    share_token: Optional[str] = Field(default=None, index=True)
    share_expires_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ResumeReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    resume_id: int = Field(foreign_key="resume.id", index=True)
    position: str
    grade: str = ""
    report_data: str = "{}"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LLMConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    base_url: str
    api_key: str
    model: str
    is_active: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ChatConversation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    title: str = "新对话"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="chatconversation.id")
    role: str
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AvatarProviderConfig(SQLModel, table=True):
    """具身交互智能体服务凭证（ASR/TTS/形象捆绑，镜像 LLMConfig 模式）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    app_id: str
    app_secret: str  # Fernet 加密存储
    gateway_server: str
    avatar_image: str = ""  # 具身交互智能体形象图片 URL
    is_active: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Avatar(SQLModel, table=True):
    """具身交互智能体形象目录（用户级选择，资源后补）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    cover_url: str = ""
    provider_config_id: Optional[int] = Field(default=None, foreign_key="avatarproviderconfig.id")
    extra: str = "{}"  # JSON 扩展字段（如 xmov avatar_id、lottie 路径等）
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AlgorithmProblem(SQLModel, table=True):
    """算法题库（P3 代码与算法练习模块）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str = ""  # Markdown 题面
    difficulty: str = "中等"  # 简单/中等/困难
    position: str = ""  # 关联岗位方向（前端/后端/通用）
    tags: str = "[]"  # JSON 数组，如 ["数组","双指针"]
    examples: str = "[]"  # JSON 数组，[{input, output, explanation}]
    test_cases: str = "[]"  # JSON 数组，[{input, expected}]（隐藏用例）
    time_limit_ms: int = 2000
    memory_limit_mb: int = 256
    is_public: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CodeSubmission(SQLModel, table=True):
    """用户代码提交记录（P3 判题结果）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    problem_id: int = Field(foreign_key="algorithmproblem.id", index=True)
    language: str  # python/javascript/...
    code: str
    status: str = "pending"  # pending/running/accepted/wrong_answer/compile_error/runtime_error/timeout
    stdout: str = ""
    stderr: str = ""
    pass_count: int = 0
    total_count: int = 0
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Recording(SQLModel, table=True):
    """面试回放录制文件记录（P4）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    interview_id: int = Field(foreign_key="interview.id", index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    stream_type: str = "audio"  # audio / video / screen
    file_key: str = ""  # storage 中的 key
    file_size: int = 0
    duration_ms: int = 0
    mime_type: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeVersion(SQLModel, table=True):
    """知识库文档版本（全量快照）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: int = Field(foreign_key="knowledgedoc.id", index=True)
    version_number: int = 1
    content: str = ""
    title: str = ""
    position: str = ""
    difficulty: str = ""
    tags: str = "[]"
    change_note: str = ""
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class KnowledgeEditLock(SQLModel, table=True):
    """知识库独占编辑锁"""
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: int = Field(foreign_key="knowledgedoc.id", unique=True, index=True)
    user_id: int = Field(foreign_key="user.id")
    locked_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime


class KnowledgeCollaborator(SQLModel, table=True):
    """知识库协作者权限"""
    id: Optional[int] = Field(default=None, primary_key=True)
    doc_id: int = Field(foreign_key="knowledgedoc.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    permission: str = "read"  # read / edit / admin
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(SQLModel, table=True):
    """站内通知"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    type: str = "system"  # collaboration / review / system
    title: str = ""
    content: str = ""
    is_read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InterviewTemplate(SQLModel, table=True):
    """面试模板（P3）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    name: str
    position: str = ""
    difficulty: str = "中等"
    duration: int = 30
    style: str = "温和"
    resume_id: Optional[int] = Field(default=None, foreign_key="resume.id")
    jd_id: Optional[int] = Field(default=None, foreign_key="jobdescription.id")
    avatar_config_id: Optional[int] = Field(default=None, foreign_key="avatarproviderconfig.id")
    code_enabled: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserQuota(SQLModel, table=True):
    """用户使用配额（P4）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    plan: str = "free"  # free / standard / enterprise
    interview_limit: int = 10
    interview_used: int = 0
    knowledge_limit: int = 20
    knowledge_used: int = 0
    ai_calls_limit: int = 100
    ai_calls_used: int = 0
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InviteCode(SQLModel, table=True):
    """邀请码（P4）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    owner_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    reward_amount: int = 5
    is_used: bool = False
    used_by: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AvatarSessionToken(SQLModel, table=True):
    """具身交互智能体 SDK 会话 Token：长时效（24h），用作 brain_config.api_key 代理 RAG+LLM 请求。"""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    token: str = Field(unique=True, index=True)
    conversation_id: int = Field(foreign_key="chatconversation.id")
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InterviewAvatarSession(SQLModel, table=True):
    """面试专用具身交互智能体会话 Token。

    与 AvatarSessionToken（聊天场景）并列：brain proxy 解析 token 时先查本表，
    命中则走「面试官大脑」（interview_brain_service），否则回落聊天链路。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    interview_id: int = Field(foreign_key="interview.id", index=True)
    token: str = Field(unique=True, index=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InterviewMetric(SQLModel, table=True):
    """面试具身链路实测指标（用于 /metrics 页面展示真实实测数据）。

    kind: ttfa(首字延迟) | tool(单次工具耗时) | e2e(端到端) | interrupt(打断延迟)
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    interview_id: int = Field(foreign_key="interview.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    kind: str = Field(index=True)
    name: str = ""
    value_ms: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserWeaknessProfile(SQLModel, table=True):
    """跨会话候选人弱点画像：每场面试报告生成后聚合，供下一场面试 prompt 注入。

    category: knowledge(知识点) | expression(表达) | logic(逻辑) | jobfit(岗位匹配)
    同一 (user_id, position, category, topic) 累加 hit_count，用于识别"反复出现"的弱点。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    position: str = Field(default="", index=True)
    category: str = "knowledge"
    topic: str = ""
    hit_count: int = 1
    severity: float = 0
    latest_score: float = 0
    evidence: str = ""
    last_interview_id: Optional[int] = Field(default=None, foreign_key="interview.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------- 企业侧（候选人初筛） ----------
# 设计要点：候选人**不是**新的账号体系，而是 role="candidate" 的无密码 User。
# 这样面试链路（stream / 报告 / 录音 / 具身播报 / 指标）全部零改动复用个人练习的那一套，
# 企业侧新增的只有「组织」「邀请」「候选人归属」这三层关系。

class Organization(SQLModel, table=True):
    """企业组织：HR 侧的数据隔离边界。

    个人练习用户不创建组织，其 Interview.org_id 恒为 NULL，行为与改造前完全一致。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = ""
    owner_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OrgMember(SQLModel, table=True):
    """组织成员。role: owner（创建者）/ hr（可发邀请、看报告）/ viewer（只看报告）"""
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="organization.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    role: str = "hr"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CandidateInvite(SQLModel, table=True):
    """候选人面试邀请：HR 创建后把链接发给候选人，候选人免注册即可作答。

    difficulty / style 沿用前端词汇（junior|mid|senior、strict|friendly|pressure），
    创建面试时再由 normalize_difficulty 与 _STYLE_DESC 转成模型可用的形式。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="organization.id", index=True)
    token: str = Field(unique=True, index=True)
    position: str
    jd_id: Optional[int] = Field(default=None, foreign_key="jobdescription.id")
    difficulty: str = "mid"
    duration: int = 30
    style: str = "friendly"
    note: str = ""
    # 本次面试的考察重点（HR 自定义，随邀请落库并注入候选人面试的 prompt）
    focus: str = ""
    created_by: int = Field(foreign_key="user.id")
    expires_at: Optional[datetime] = None
    revoked: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Candidate(SQLModel, table=True):
    """候选人：凭邀请链接进入后创建，落库为 role="candidate" 的无密码 User。

    真正作答的是 user_id 指向的那个 User；本表只承载「姓名/联系方式 + 归属哪次邀请」。
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    invite_id: int = Field(foreign_key="candidateinvite.id", index=True)
    org_id: int = Field(foreign_key="organization.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str = ""
    email: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
