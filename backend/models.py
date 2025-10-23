from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class PresignRequest(BaseModel):
    ext: Literal["pdf", "docx"]


class PresignResponse(BaseModel):
    key: str
    url: str
    headers: dict = Field(default_factory=dict)
    content_type: str


class AnalyzeRequest(BaseModel):
    s3_key: str


class Issue(BaseModel):
    issue_id: str
    category: str
    severity: Literal["low", "medium", "high", "critical"]
    risk_summary: str
    recommendation: str
    exact_text_snippet: Optional[str] = None
    page_hint: Optional[int] = None
    page_numbers: List[int] = Field(default_factory=list)
    redline_suggestion: Optional[str] = None


class AnalyzeResult(BaseModel):
    issues: List[Issue]
    summary: str
    total_issues: int


class HealthResponse(BaseModel):
    status: str
    region: str
    model_id: str
    bucket: str
    limits: dict

