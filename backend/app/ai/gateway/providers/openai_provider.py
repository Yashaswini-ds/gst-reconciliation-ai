import json
from typing import Optional

import httpx

from app.ai.gateway.base_provider import BaseAIProvider
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
from app.ai.prompts import (
    CANDIDATE_RESOLUTION_SYSTEM_PROMPT,
    DISCREPANCY_REVIEW_SYSTEM_PROMPT,
    RESOLUTION_RECOMMENDATION_SYSTEM_PROMPT,
    SCHEMA_MAPPING_SYSTEM_PROMPT,
    SOURCE_ROLE_DETECTION_SYSTEM_PROMPT,
)


class OpenAIAIProvider(BaseAIProvider):
    """OpenAI Live API AI Provider using Chat Completions JSON Mode."""

    def __init__(self, api_key: str, model_name: str = "gpt-4o"):
        if not api_key:
            raise ValueError("OpenAI API key is required.")
        self._api_key = api_key
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_identifier(self) -> str:
        return self._model_name

    async def _post_chat_completion(self, system_prompt: str, user_prompt: str) -> dict:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)

    async def map_schema(self, request: AISchemaMappingRequest) -> AISchemaMappingResponse:
        system_prompt = SCHEMA_MAPPING_SYSTEM_PROMPT
        user_prompt = f"Source columns to map: {json.dumps(request.source_columns)}"
        data = await self._post_chat_completion(system_prompt, user_prompt)
        return AISchemaMappingResponse.model_validate(data)

    async def resolve_candidate_ambiguity(
        self, request: AICandidateResolutionRequest
    ) -> AICandidateResolutionResponse:
        system_prompt = CANDIDATE_RESOLUTION_SYSTEM_PROMPT
        user_prompt = (
            f"GST Record: {request.gst_record.model_dump_json()}\n"
            f"Candidate ERP Records: {[c.model_dump_json() for c in request.candidate_erp_records]}"
        )
        data = await self._post_chat_completion(system_prompt, user_prompt)
        return AICandidateResolutionResponse.model_validate(data)

    async def review_discrepancy(
        self, request: AIDiscrepancyReviewRequest
    ) -> AIDiscrepancyReviewResponse:
        system_prompt = DISCREPANCY_REVIEW_SYSTEM_PROMPT
        res = request.reconciliation_result
        evidence = {
            "invoice_number": res.gst_record.invoice_number if res.gst_record else (res.erp_record.invoice_number if res.erp_record else None),
            "supplier_gstin": res.gst_record.gstin if res.gst_record else (res.erp_record.gstin if res.erp_record else None),
            "classification": res.classification.value,
            "unmatched_reason": res.unmatched_reason.value if res.unmatched_reason else None,
            "field_differences": [
                {
                    "field_name": diff.field_name,
                    "gst_value": str(diff.gst_value),
                    "erp_value": str(diff.erp_value),
                    "difference_amount": diff.difference_amount
                }
                for diff in res.field_differences
            ],
            "remarks": res.remarks
        }
        user_prompt = f"Reconciliation Discrepancy Evidence: {json.dumps(evidence)}"
        data = await self._post_chat_completion(system_prompt, user_prompt)
        return AIDiscrepancyReviewResponse.model_validate(data)

    async def generate_resolution_recommendation(
        self, request: AIResolutionRequest
    ) -> AIResolutionResponse:
        system_prompt = RESOLUTION_RECOMMENDATION_SYSTEM_PROMPT
        user_prompt = f"Reconciliation Result: {request.reconciliation_result.model_dump_json()}\nSupplier: {request.supplier_name}"
        data = await self._post_chat_completion(system_prompt, user_prompt)
        return AIResolutionResponse.model_validate(data)

    async def detect_source_role(
        self, request: AIPairwiseSourceRoleRequest
    ) -> AIPairwiseSourceRoleResponse:
        system_prompt = SOURCE_ROLE_DETECTION_SYSTEM_PROMPT
        user_prompt = f"GST Slot Headers: {json.dumps(request.gst_columns)}\nERP Slot Headers: {json.dumps(request.erp_columns)}"
        data = await self._post_chat_completion(system_prompt, user_prompt)
        res = AIPairwiseSourceRoleResponse.model_validate(data)

        if res.gst_role not in ["GST_LIKELY", "ERP_LIKELY", "AMBIGUOUS"]:
            res.gst_role = "AMBIGUOUS"
        if res.erp_role not in ["GST_LIKELY", "ERP_LIKELY", "AMBIGUOUS"]:
            res.erp_role = "AMBIGUOUS"

        if res.gst_role == "ERP_LIKELY" or res.erp_role == "GST_LIKELY" or res.assignment_valid is False:
            res.assignment_valid = False

        if res.confidence < 0.70 and res.assignment_valid is True:
            res.gst_role = "AMBIGUOUS"
            res.erp_role = "AMBIGUOUS"

        return res

