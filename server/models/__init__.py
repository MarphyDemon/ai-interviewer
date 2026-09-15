import os
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
    position: str
    difficulty: str
    duration: int = 30
    style: str = "温和"
    status: str = "进行中"
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
