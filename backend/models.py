"""
Pydantic request/response models for the Prism API.
"""

from typing import Any
from pydantic import BaseModel


class AISettings(BaseModel):
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    openai_model: str = "gpt-4o-mini"
    anthropic_model: str = "claude-sonnet-4-6"
    screenshot_service_url: str = "http://screenshot:3000"
    max_deep_pages: int = 20


class AnalyzeRequest(BaseModel):
    url: str
    settings: AISettings
    task_id: str | None = None  # client-provided ID for cancellation
    scan_mode: str = "shallow"  # "shallow" | "deep" | "batch"
    vision_mode: bool = False  # True = skip HTML extraction, use up to 2 screenshots


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 20


class EmailSettings(BaseModel):
    ai_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    anthropic_model: str = "claude-sonnet-4-6"
    your_name: str = "Marcin Zielinski"
    your_title: str = "English Localization Specialist"
    your_email: str = ""
    your_website: str = "https://imrie83.github.io/shinrai/"


class GenerateEmailRequest(BaseModel):
    scan_result: dict[str, Any]
    settings: EmailSettings
    dashboard_screenshot: str | None = None


class SendEmailSettings(BaseModel):
    your_name: str = "Marcin Zielinski"
    from_address: str = ""


class SendEmailRequest(BaseModel):
    to: str
    subject: str
    html: str
    url: str = ""
    settings: SendEmailSettings


class ScheduleEmailRequest(BaseModel):
    to: str
    subject: str
    html: str
    url: str = ""
    settings: SendEmailSettings
    scheduled_at: str


class CancelScheduleRequest(BaseModel):
    url: str


class AgentMessage(BaseModel):
    role: str
    content: str


class AgentChatRequest(BaseModel):
    messages: list[AgentMessage]
    scan_context: str
    settings: AISettings


class RebuildCardRequest(BaseModel):
    scan_result: dict[str, Any]
    selected_issue_indices: list[int]


class SaveEmailDraftRequest(BaseModel):
    html: str


class DiscoverSearchRequest(BaseModel):
    keywords: str
    location: str = ""
    limit: int = 120
