import pytest
from app.ai.gateway import (
    AICandidateResolutionRequest,
    AIDiscrepancyReviewRequest,
    AIGateway,
    AISchemaMappingRequest,
    BaseAIProvider,
    FallbackAIProvider,
)
from app.mapping.schemas import CanonicalInvoice
from app.matching.schemas import MatchClassification, ReconciliationRecordResult


class FailingAIProvider(BaseAIProvider):
    """Failing mock provider to test AI Gateway exception handling and fallback recovery."""

    @property
    def provider_name(self) -> str:
        return "failing-mock"

    @property
    def model_identifier(self) -> str:
        return "mock-v1"

    async def map_schema(self, request):
        raise RuntimeError("Simulated external LLM API timeout")

    async def resolve_candidate_ambiguity(self, request):
        raise RuntimeError("Simulated invalid LLM JSON payload")

    async def review_discrepancy(self, request):
        raise RuntimeError("Simulated rate limit exceeded")


def make_invoice(inv_num="INV-100", gstin="27AAAAA0000A1Z5"):
    return CanonicalInvoice(
        invoice_number=inv_num,
        gstin=gstin,
        invoice_date="2024-04-01",
        taxable_value=1000.0,
        cgst=90.0,
        sgst=90.0,
        igst=0.0,
        total_invoice_value=1180.0,
    )


@pytest.mark.asyncio
async def test_ai_gateway_schema_mapping_fallback():
    gateway = AIGateway()
    req = AISchemaMappingRequest(source_columns=["Invoice Number", "Vendor_GSTIN", "Random_Header"])

    resp, meta = await gateway.map_schema(req)

    assert len(resp.suggestions) == 3
    assert resp.suggestions[0].canonical_field == "invoice_number"
    assert resp.suggestions[1].canonical_field == "gstin"
    assert resp.suggestions[2].canonical_field is None

    assert meta.task_type == "SCHEMA_MAPPING"
    assert meta.fallback_used is False  # Fallback provider was primary
    assert meta.validation_passed is True


@pytest.mark.asyncio
async def test_ai_gateway_candidate_ambiguity_fallback():
    gateway = AIGateway()
    gst_rec = make_invoice("INV-100")
    erp_cand = make_invoice("INV100")

    req = AICandidateResolutionRequest(
        gst_record=gst_rec,
        candidate_erp_records=[erp_cand],
    )

    resp, meta = await gateway.resolve_candidate_ambiguity(req)

    assert resp.selected_candidate_invoice_number == "INV100"
    assert resp.confidence > 0.0
    assert meta.task_type == "CANDIDATE_RESOLUTION"
    assert meta.validation_passed is True


@pytest.mark.asyncio
async def test_ai_gateway_discrepancy_review_fallback():
    gateway = AIGateway()
    rec_result = ReconciliationRecordResult(
        gst_record=make_invoice(),
        erp_record=make_invoice(),
        classification=MatchClassification.EXACT_MATCH,
    )

    req = AIDiscrepancyReviewRequest(reconciliation_result=rec_result)
    resp, meta = await gateway.review_discrepancy(req)

    assert "EXACT_MATCH" in resp.ai_remark or "EXACT_MATCH" in resp.audit_remark
    assert meta.task_type == "DISCREPANCY_REVIEW"
    assert meta.validation_passed is True



@pytest.mark.asyncio
async def test_ai_gateway_provider_failure_graceful_fallback():
    failing_provider = FailingAIProvider()
    gateway = AIGateway(provider=failing_provider)

    req = AISchemaMappingRequest(source_columns=["Invoice Number"])
    resp, meta = await gateway.map_schema(req)

    # Must fall back gracefully to deterministic rules
    assert resp.suggestions[0].canonical_field == "invoice_number"
    assert meta.fallback_used is True
    assert meta.validation_passed is False
