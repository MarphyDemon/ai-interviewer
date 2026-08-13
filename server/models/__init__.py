import os
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    anonymous_uuid: str = Field(unique=True, index=True)
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
