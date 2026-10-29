import time
from typing import Optional, Tuple

from app.ai.gateway.base_provider import BaseAIProvider
from app.ai.gateway.fallback_provider import FallbackAIProvider
from app.ai.gateway.schemas import (
    AICandidateResolutionRequest,
    AICandidateResolutionResponse,
    AIDiscrepancyReviewRequest,
    AIDiscrepancyReviewResponse,
    AIGatewayMetadata,
    AIPairwiseSourceRoleRequest,
    AIPairwiseSourceRoleResponse,
    AIResolutionRequest,
    AIResolutionResponse,
    AISchemaMappingRequest,
    AISchemaMappingResponse,
)


def create_default_provider() -> BaseAIProvider:
    """Instantiates active provider based on environment settings with fallback safety."""
    from app.core.config import settings
    provider_name = (settings.AI_PROVIDER or "fallback").lower().strip()

    if provider_name == "openai" and settings.OPENAI_API_KEY:
        try:
            from app.ai.gateway.providers.openai_provider import OpenAIAIProvider
            return OpenAIAIProvider(api_key=settings.OPENAI_API_KEY, model_name=settings.LLM_MODEL)
        except Exception:
            pass

    if provider_name == "gemini" or (settings.GEMINI_API_KEY and provider_name != "openai"):
        if settings.GEMINI_API_KEY:
            try:
                from app.ai.gateway.providers.gemini_provider import GeminiAIProvider
                return GeminiAIProvider(
                    api_key=settings.GEMINI_API_KEY,
                    model_name=settings.GEMINI_MODEL or "gemini-1.5-flash"
                )
            except Exception:
                pass
        return FallbackAIProvider()

    return FallbackAIProvider()


class AIGateway:
    """Centralized AI Gateway managing AI task delegation, response validation, and deterministic fallbacks."""

    def __init__(
        self,
        provider: Optional[BaseAIProvider] = None,
        fallback_provider: Optional[BaseAIProvider] = None,
    ):
        self.fallback_provider = fallback_provider or FallbackAIProvider()
        self.provider = provider or create_default_provider()

    def set_provider(self, provider: BaseAIProvider):
        """Dynamically sets active AI provider."""
        self.provider = provider


    async def map_schema(
        self, request: AISchemaMappingRequest
    ) -> Tuple[AISchemaMappingResponse, AIGatewayMetadata]:
        """Executes schema mapping task with provider-agnostic validation and fallback protection."""
        start_time = time.perf_counter()
        fallback_used = False
        validation_passed = True

        try:
            response = await self.provider.map_schema(request)
            validated_response = AISchemaMappingResponse.model_validate(response)
        except Exception:
            fallback_used = True
            validation_passed = False
            validated_response = await self.fallback_provider.map_schema(request)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        avg_confidence = (
            sum(s.confidence for s in validated_response.suggestions) / len(validated_response.suggestions)
            if validated_response.suggestions
            else 0.0
        )

        metadata = AIGatewayMetadata(
            task_type="SCHEMA_MAPPING",
            provider_name=self.fallback_provider.provider_name if fallback_used else self.provider.provider_name,
            model_identifier=self.fallback_provider.model_identifier if fallback_used else self.provider.model_identifier,
            latency_ms=latency_ms,
            confidence=round(avg_confidence, 2),
            fallback_used=fallback_used,
            validation_passed=validation_passed,
        )

        return validated_response, metadata

    async def resolve_candidate_ambiguity(
        self, request: AICandidateResolutionRequest
    ) -> Tuple[AICandidateResolutionResponse, AIGatewayMetadata]:
        """Executes candidate ambiguity resolution with provider-agnostic validation and fallback protection."""
        start_time = time.perf_counter()
        fallback_used = False
        validation_passed = True

        try:
            response = await self.provider.resolve_candidate_ambiguity(request)
            validated_response = AICandidateResolutionResponse.model_validate(response)
        except Exception:
            fallback_used = True
            validation_passed = False
            validated_response = await self.fallback_provider.resolve_candidate_ambiguity(request)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        metadata = AIGatewayMetadata(
            task_type="CANDIDATE_RESOLUTION",
            provider_name=self.fallback_provider.provider_name if fallback_used else self.provider.provider_name,
            model_identifier=self.fallback_provider.model_identifier if fallback_used else self.provider.model_identifier,
            latency_ms=latency_ms,
            confidence=validated_response.confidence,
            fallback_used=fallback_used,
            validation_passed=validation_passed,
        )

        return validated_response, metadata

    async def review_discrepancy(
        self, request: AIDiscrepancyReviewRequest
    ) -> Tuple[AIDiscrepancyReviewResponse, AIGatewayMetadata]:
        """Executes post-reconciliation discrepancy review with provider-agnostic validation and fallback protection."""
        start_time = time.perf_counter()
        fallback_used = False
        validation_passed = True

        try:
            response = await self.provider.review_discrepancy(request)
            validated_response = AIDiscrepancyReviewResponse.model_validate(response)
        except Exception:
            fallback_used = True
            validation_passed = False
            validated_response = await self.fallback_provider.review_discrepancy(request)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        metadata = AIGatewayMetadata(
            task_type="DISCREPANCY_REVIEW",
            provider_name=self.fallback_provider.provider_name if fallback_used else self.provider.provider_name,
            model_identifier=self.fallback_provider.model_identifier if fallback_used else self.provider.model_identifier,
            latency_ms=latency_ms,
            confidence=1.0,
            fallback_used=fallback_used,
            validation_passed=validation_passed,
        )

        return validated_response, metadata

    async def generate_resolution(
        self, request: AIResolutionRequest
    ) -> Tuple[AIResolutionResponse, AIGatewayMetadata]:
        """Executes resolution recommendation task with validation and fallback protection."""
        start_time = time.perf_counter()
        fallback_used = False
        validation_passed = True

        try:
            response = await self.provider.generate_resolution_recommendation(request)
            validated_response = AIResolutionResponse.model_validate(response)
        except Exception:
            fallback_used = True
            validation_passed = False
            validated_response = await self.fallback_provider.generate_resolution_recommendation(request)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        metadata = AIGatewayMetadata(
            task_type="RESOLUTION_RECOMMENDATION",
            provider_name=self.fallback_provider.provider_name if fallback_used else self.provider.provider_name,
            model_identifier=self.fallback_provider.model_identifier if fallback_used else self.provider.model_identifier,
            latency_ms=latency_ms,
            confidence=validated_response.confidence_score,
            fallback_used=fallback_used,
            validation_passed=validation_passed,
        )

        return validated_response, metadata

    async def detect_source_role(
        self, request: AIPairwiseSourceRoleRequest
    ) -> Tuple[AIPairwiseSourceRoleResponse, AIGatewayMetadata]:
        """Executes pairwise file source role detection with provider-agnostic validation and fallback protection."""
        start_time = time.perf_counter()
        fallback_used = False
        validation_passed = True

        try:
            validated_response = await self.provider.detect_source_role(request)
        except Exception:
            fallback_used = True
            validation_passed = False
            validated_response = await self.fallback_provider.detect_source_role(request)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        metadata = AIGatewayMetadata(
            task_type="SOURCE_ROLE",
            provider_name=self.fallback_provider.provider_name if fallback_used else self.provider.provider_name,
            model_identifier=self.fallback_provider.model_identifier if fallback_used else self.provider.model_identifier,
            latency_ms=latency_ms,
            confidence=validated_response.confidence,
            fallback_used=fallback_used,
            validation_passed=validation_passed,
        )

        return validated_response, metadata



ai_gateway = AIGateway()
