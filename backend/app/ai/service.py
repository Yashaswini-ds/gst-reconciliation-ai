import difflib
from typing import List, Optional

from app.ai.schemas import (
    AICandidateResolutionResponse,
    AIDiscrepancyReviewResponse,
    AIPairwiseSourceRoleResponse,
    AIResolutionRequest,
    AIResolutionResponse,
)
from app.mapping.schemas import CanonicalInvoice
from app.matching.schemas import MatchClassification, ReconciliationRecordResult


class AIService:
    """AI Service handling candidate ambiguity resolution, post-reconciliation reviews, and resolution vouchers.

    Strictly complies with SDD guidelines:
    - Does NOT perform basic arithmetic or financial tolerance calculations.
    - Operates on structured evidence payloads.
    - Routes low confidence candidates (< 0.80) to manual review.
    """

    async def resolve_candidate_ambiguity_async(
        self, gst_record: CanonicalInvoice, candidate_erp_records: List[CanonicalInvoice]
    ) -> AICandidateResolutionResponse:
        """Resolves ambiguous candidate ERP matches via AI Gateway with candidate validation & safety checks."""
        if not candidate_erp_records:
            return AICandidateResolutionResponse(
                selected_candidate_invoice_number=None,
                confidence=0.0,
                evidence=["No ERP candidates provided."],
                reasoning="No candidate records were provided for ambiguity resolution.",
                requires_manual_review=True,
            )

        from app.ai.gateway import ai_gateway, AICandidateResolutionRequest

        req = AICandidateResolutionRequest(
            gst_record=gst_record,
            candidate_erp_records=candidate_erp_records,
        )

        try:
            response, metadata = await ai_gateway.resolve_candidate_ambiguity(req)

            # Safety Validation: Ensure selected candidate exists in supplied list
            supplied_inv_numbers = {
                cand.invoice_number.strip().upper()
                for cand in candidate_erp_records
                if cand.invoice_number
            }

            selected_inv = response.selected_candidate_invoice_number
            if selected_inv:
                selected_inv_clean = selected_inv.strip().upper()
                if selected_inv_clean not in supplied_inv_numbers:
                    # AI invented an unlisted candidate -> Reject & flag manual review
                    return AICandidateResolutionResponse(
                        selected_candidate_invoice_number=None,
                        confidence=0.0,
                        evidence=response.evidence + ["Rejected unlisted AI candidate recommendation."],
                        reasoning=f"AI suggested candidate '{selected_inv}' which was not in supplied ERP candidate list.",
                        requires_manual_review=True,
                    )

            requires_review = (
                response.confidence < 0.80
                or response.requires_manual_review
                or metadata.fallback_used
            )

            return AICandidateResolutionResponse(
                selected_candidate_invoice_number=selected_inv,
                confidence=response.confidence,
                evidence=response.evidence,
                reasoning=response.reasoning,
                requires_manual_review=requires_review,
            )

        except Exception as exc:
            return AICandidateResolutionResponse(
                selected_candidate_invoice_number=None,
                confidence=0.0,
                evidence=["AI Gateway resolution failed."],
                reasoning=f"AI Gateway resolution encountered exception: {str(exc)}",
                requires_manual_review=True,
            )

    def resolve_candidate_ambiguity(
        self, gst_record: CanonicalInvoice, candidate_erp_records: List[CanonicalInvoice]
    ) -> AICandidateResolutionResponse:
        """Synchronous wrapper for candidate ambiguity resolution."""
        import asyncio
        try:
            return asyncio.run(
                self.resolve_candidate_ambiguity_async(gst_record, candidate_erp_records)
            )
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.resolve_candidate_ambiguity_async(gst_record, candidate_erp_records),
                )
                return future.result()


    async def review_discrepancy_async(
        self, result: ReconciliationRecordResult
    ) -> AIDiscrepancyReviewResponse:
        """Analyzes deterministic reconciliation results via AI Gateway to generate human-readable explanations.

        Does NOT perform arithmetic or alter numeric values.
        """
        from app.ai.gateway import ai_gateway, AIDiscrepancyReviewRequest

        req = AIDiscrepancyReviewRequest(reconciliation_result=result)

        try:
            response, _ = await ai_gateway.review_discrepancy(req)
            return response
        except Exception:
            # Deterministic fallback response if gateway fails
            return AIDiscrepancyReviewResponse(
                explanation="Discrepancy review generated via deterministic fallback.",
                ai_remark=f"{result.classification.value}: Field evaluation completed.",
                audit_remark="Manual review recommended prior to ITC claim filing.",
                recommended_action="Inspect field differences and vendor invoice document.",
            )

    def review_discrepancy(self, result: ReconciliationRecordResult) -> AIDiscrepancyReviewResponse:
        """Synchronous wrapper for post-reconciliation discrepancy review."""
        import asyncio
        try:
            return asyncio.run(self.review_discrepancy_async(result))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.review_discrepancy_async(result))
                return future.result()


    async def generate_resolution_recommendation_async(
        self, result: ReconciliationRecordResult, supplier_name: Optional[str] = None
    ) -> AIResolutionResponse:
        """Generates AI resolution suggestion, accounting voucher, and notice draft for a single result."""
        from app.ai.gateway import ai_gateway

        req = AIResolutionRequest(reconciliation_result=result, supplier_name=supplier_name)
        try:
            response, _ = await ai_gateway.generate_resolution(req)
            return response
        except Exception as exc:
            return AIResolutionResponse(
                action_type="CONTACT_VENDOR",
                summary="Encountered error generating resolution recommendations.",
                reasoning=f"AI Gateway resolution request failed: {str(exc)}",
                adjustment_voucher=None,
                vendor_notice=None,
                confidence_score=0.0,
            )

    def generate_resolution_recommendation(
        self, result: ReconciliationRecordResult, supplier_name: Optional[str] = None
    ) -> AIResolutionResponse:
        """Synchronous wrapper for generating resolution recommendations."""
        import asyncio
        try:
            return asyncio.run(self.generate_resolution_recommendation_async(result, supplier_name))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.generate_resolution_recommendation_async(result, supplier_name)
                )
                return future.result()

    async def batch_generate_resolutions_async(
        self, results: List[ReconciliationRecordResult]
    ) -> List[AIResolutionResponse]:
        """Generates AI resolution recommendations for multiple reconciliation results in batch."""
        import asyncio
        tasks = [
            self.generate_resolution_recommendation_async(res)
            for res in results
        ]
        return await asyncio.gather(*tasks)

    def batch_generate_resolutions(
        self, results: List[ReconciliationRecordResult]
    ) -> List[AIResolutionResponse]:
        """Synchronous wrapper for batch generating resolution recommendations."""
        import asyncio
        try:
            return asyncio.run(self.batch_generate_resolutions_async(results))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.batch_generate_resolutions_async(results))
                return future.result()

    async def detect_source_role_async(
        self, gst_columns: List[str], erp_columns: List[str]
    ) -> AIPairwiseSourceRoleResponse:
        """Determines pairwise file source roles (GST_LIKELY, ERP_LIKELY, AMBIGUOUS) via AI Gateway."""
        from app.ai.gateway import ai_gateway, AIPairwiseSourceRoleRequest

        req = AIPairwiseSourceRoleRequest(gst_columns=gst_columns, erp_columns=erp_columns)
        try:
            response, _ = await ai_gateway.detect_source_role(req)
            return response
        except Exception:
            return AIPairwiseSourceRoleResponse(
                gst_role="AMBIGUOUS",
                erp_role="AMBIGUOUS",
                assignment_valid=True,
                confidence=0.5,
                reasoning="Fallback: Pairwise role detection fallback due to gateway error."
            )


ai_service = AIService()

