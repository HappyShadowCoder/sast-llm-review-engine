from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


CategoryType = Literal["architecture", "security", "performance", "concurrency", "bug", "style_nitpick"]
SeverityType = Literal["critical", "high", "medium", "low"]


class SASTFinding(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: str = Field(..., description="Semgrep rule identifier e.g. python.lang.security.injection")
    file_path: str = Field(..., description="Path to file")
    start_line: int = Field(..., ge=1)
    end_line: int = Field(..., ge=1)
    message: str = Field(..., description="Vulnerability description from SAST rule")
    severity: str = Field("high", description="INFO | WARNING | ERROR / critical | high | medium")
    cwe: Optional[str] = None
    snippet: str = ""


class ReviewFinding(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_path: str = Field(..., description="Target file path relative to repo root")
    start_line: int = Field(..., ge=1, description="1-based starting line number")
    end_line: int = Field(..., ge=1, description="1-based ending line number")
    category: CategoryType = Field(..., description="architecture | security | performance | concurrency | bug")
    severity: SeverityType = Field(..., description="critical | high | medium")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    explanation: str = Field(..., min_length=1, description="Clear technical explanation of the issue")
    suggested_code: str = Field(..., description="Exact replacement block for lines [start_line, end_line]")

    @field_validator("end_line")
    @classmethod
    def validate_line_range(cls, v: int, info) -> int:
        start_line = info.data.get("start_line")
        if start_line is not None and v < start_line:
            raise ValueError(f"end_line ({v}) cannot be less than start_line ({start_line})")
        return v

    def is_noise(self, min_confidence: float = 0.80) -> bool:
        """Anti-noise gate: drop if confidence < 0.80 or category == 'style_nitpick'."""
        if self.confidence < min_confidence:
            return True
        if self.category == "style_nitpick":
            return True
        return False


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    summary: str = Field(..., description="High-level architectural assessment")
    findings: List[ReviewFinding] = Field(default_factory=list)


class FormattedComment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_path: str
    start_line: int
    end_line: int
    body: str
    category: str
    severity: str
    confidence: float
    raw_suggested_code: str
