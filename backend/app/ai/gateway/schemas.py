from typing import List, Optional
from pydantic import BaseModel, Field

from app.ai.schemas import (
    AICandidateResolutionRequest,
    AICandidateResolutionResponse,
    AIDiscrepancyReviewRequest,
    AIDiscrepancyReviewResponse,
    AIPairwiseSourceRoleRequest,
    AIPairwiseSourceRoleResponse,
    AIResolutionRequest,
    AIResolutionResponse,
)


class ColumnMappingSuggestion(BaseModel):
    """Structured suggestion for mapping a source column to a canonical field."""

    source_column: str = Field(..., description="Original column header from source file")
    canonical_field: Optional[str] = Field(None, description="Suggested canonical field name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence rating of mapping suggestion")
    evidence: str = Field(..., description="Supporting evidence for mapping decision")
    reasoning: str = Field(..., description="Detailed explanation of header mapping decision")


class AISchemaMappingRequest(BaseModel):
    """Payload requesting AI assistance for mapping source column headers."""

    source_columns: List[str] = Field(..., description="List of unmapped source file column headers")
    source_type: str = Field("GST", description="Dataset source type (GST or ERP)")


class AISchemaMappingResponse(BaseModel):
    """Structured response contract for AI schema mapping suggestions."""

    suggestions: List[ColumnMappingSuggestion] = Field(default=[], description="List of header mapping suggestions")


class AIGatewayMetadata(BaseModel):
    """Audit metadata recorded for every AI Gateway invocation."""

    task_type: str = Field(..., description="Task type (SCHEMA_MAPPING | CANDIDATE_RESOLUTION | DISCREPANCY_REVIEW)")
    provider_name: str = Field(..., description="Name of AI Provider (fallback | openai | gemini)")
    model_identifier: str = Field(..., description="Model identifier used")
    latency_ms: float = Field(..., ge=0.0, description="Invocation latency in milliseconds")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall task confidence score")
    fallback_used: bool = Field(False, description="True if deterministic fallback provider was invoked")
    validation_passed: bool = Field(True, description="True if response schema validation passed")
