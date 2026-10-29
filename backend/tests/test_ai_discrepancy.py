import pytest
from app.ai.gateway import (
    AIDiscrepancyReviewResponse,
    BaseAIProvider,
)
from app.ai.service import ai_service
from app.mapping.schemas import CanonicalInvoice
from app.matching.schemas import FieldDifference, MatchClassification, ReconciliationRecordResult


class CustomDiscrepancyProvider(BaseAIProvider):
    @property
    def provider_name(self) -> str:
        return "custom-discrepancy-mock"

    @property
    def model_identifier(self) -> str:
        return "mock-v1"

    async def map_schema(self, request):
        raise NotImplementedError()

    async def resolve_candidate_ambiguity(self, request):
        raise NotImplementedError()

    async def review_discrepancy(self, request):
        return AIDiscrepancyReviewResponse(
            explanation="Mock AI explanation for field difference.",
            ai_remark="DISCREPANCY_MOCK: Tax head discrepancy observed.",
            audit_remark="Flagged for manual compliance audit.",
            recommended_action="Contact supplier for debit note.",
        )


def make_invoice(inv_num="INV-100", total=1180.0):
    return CanonicalInvoice(
        invoice_number=inv_num,
        gstin="27AAAAA0000A1Z5",
        invoice_date="2024-04-01",
        taxable_value=1000.0,
        cgst=90.0,
        sgst=90.0,
        igst=0.0,
        total_invoice_value=total,
    )


@pytest.mark.asyncio
async def test_ai_discrepancy_review_exact_match():
    res = ReconciliationRecordResult(
        gst_record=make_invoice(),
        erp_record=make_invoice(),
        classification=MatchClassification.EXACT_MATCH,
    )

    resp = await ai_service.review_discrepancy_async(res)
    assert resp.explanation != ""
    assert resp.ai_remark != ""
    assert resp.audit_remark != ""


@pytest.mark.asyncio
async def test_ai_discrepancy_review_with_custom_provider():
    res = ReconciliationRecordResult(
        gst_record=make_invoice(total=1180.0),
        erp_record=make_invoice(total=1500.0),
        classification=MatchClassification.DISCREPANCY,
        field_differences=[
            FieldDifference(
                field_name="total_invoice_value",
                gst_value=1180.0,
                erp_value=1500.0,
                difference_amount=320.0,
                is_within_tolerance=False,
                is_critical=True,
            )
        ],
    )

    from app.ai.gateway import ai_gateway
    orig = ai_gateway.provider
    ai_gateway.set_provider(CustomDiscrepancyProvider())

    try:
        resp = await ai_service.review_discrepancy_async(res)
        assert "DISCREPANCY_MOCK" in resp.ai_remark
        assert resp.recommended_action == "Contact supplier for debit note."
    finally:
        ai_gateway.set_provider(orig)


@pytest.mark.asyncio
async def test_ai_discrepancy_review_gateway_exception_fallback():
    class ExceptionProvider(BaseAIProvider):
        @property
        def provider_name(self) -> str:
            return "exception-mock"

        @property
        def model_identifier(self) -> str:
            return "mock-v1"

        async def map_schema(self, request):
            pass

        async def resolve_candidate_ambiguity(self, request):
            pass

        async def review_discrepancy(self, request):
            raise RuntimeError("LLM Service Outage")

    from app.ai.gateway import ai_gateway
    orig = ai_gateway.provider
    ai_gateway.set_provider(ExceptionProvider())

    try:
        res = ReconciliationRecordResult(
            gst_record=make_invoice(),
            erp_record=make_invoice(),
            classification=MatchClassification.DISCREPANCY,
        )
        resp = await ai_service.review_discrepancy_async(res)
        # Exception handled gracefully via fallback
        assert resp.explanation != ""
        assert "DISCREPANCY" in resp.ai_remark
    finally:
        ai_gateway.set_provider(orig)
