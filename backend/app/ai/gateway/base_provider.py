from abc import ABC, abstractmethod
from app.ai.gateway.schemas import (
    AICandidateResolutionRequest,
    AICandidateResolutionResponse,
    AIDiscrepancyReviewRequest,
    AIDiscrepancyReviewResponse,
    AIPairwiseSourceRoleRequest,
    AIPairwiseSourceRoleResponse,
    AIResolutionRequest,
    AIResolutionResponse,
    AISchemaMappingRequest,
    AISchemaMappingResponse,
)


class BaseAIProvider(ABC):
    """Abstract Base Class for AI Model Providers (OpenAI, Gemini, Ollama, Fallback)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns provider identifier name."""
        pass

    @property
    @abstractmethod
    def model_identifier(self) -> str:
        """Returns model version identifier."""
        pass

    @abstractmethod
    async def map_schema(self, request: AISchemaMappingRequest) -> AISchemaMappingResponse:
        """Provides schema mapping suggestions for unmapped source headers."""
        pass

    @abstractmethod
    async def resolve_candidate_ambiguity(
        self, request: AICandidateResolutionRequest
    ) -> AICandidateResolutionResponse:
        """Evaluates candidate evidence for ambiguous candidate pairs."""
        pass

    @abstractmethod
    async def review_discrepancy(
        self, request: AIDiscrepancyReviewRequest
    ) -> AIDiscrepancyReviewResponse:
        """Generates explanatory notes for non-exact reconciliation records."""
        pass

    async def generate_resolution_recommendation(
        self, request: AIResolutionRequest
    ) -> AIResolutionResponse:
        """Generates accounting resolution recommendations, voucher entry, and vendor notice."""
        raise NotImplementedError("This provider does not implement generate_resolution_recommendation.")

    async def detect_source_role(
        self, request: AIPairwiseSourceRoleRequest
    ) -> AIPairwiseSourceRoleResponse:
        """Detects file source roles (GST_LIKELY, ERP_LIKELY, AMBIGUOUS) based on pairwise column headers."""
        return AIPairwiseSourceRoleResponse(
            gst_role="AMBIGUOUS",
            erp_role="AMBIGUOUS",
            assignment_valid=True,
            confidence=0.5,
            reasoning="Base provider default implementation."
        )


