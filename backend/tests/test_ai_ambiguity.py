import pytest
from app.ai.gateway import (
    AICandidateResolutionResponse,
    BaseAIProvider,
)
from app.ai.service import ai_service
from app.mapping.schemas import CanonicalInvoice


class CustomAmbiguityProvider(BaseAIProvider):
    def __init__(self, selected_inv, confidence, reasoning="Test reasoning"):
        self._selected_inv = selected_inv
        self._confidence = confidence
        self._reasoning = reasoning

    @property
    def provider_name(self) -> str:
        return "custom-ambiguity-mock"

    @property
    def model_identifier(self) -> str:
        return "mock-v1"

    async def map_schema(self, request):
        raise NotImplementedError()

    async def resolve_candidate_ambiguity(self, request):
        requires_review = self._confidence < 0.80
        return AICandidateResolutionResponse(
            selected_candidate_invoice_number=self._selected_inv,
            confidence=self._confidence,
            evidence=["Field similarity match"],
            reasoning=self._reasoning,
            requires_manual_review=requires_review,
        )

    async def review_discrepancy(self, request):
        raise NotImplementedError()


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
async def test_ai_ambiguity_successful_resolution():
    gst_rec = make_invoice("INV-100")
    cand1 = make_invoice("INV100")
    cand2 = make_invoice("INV-999")

    mock_provider = CustomAmbiguityProvider(selected_inv="INV100", confidence=0.92)

    from app.ai.gateway import ai_gateway
    orig = ai_gateway.provider
    ai_gateway.set_provider(mock_provider)

    try:
        resp = await ai_service.resolve_candidate_ambiguity_async(gst_rec, [cand1, cand2])
        assert resp.selected_candidate_invoice_number == "INV100"
        assert resp.confidence == 0.92
        assert resp.requires_manual_review is False
    finally:
        ai_gateway.set_provider(orig)


@pytest.mark.asyncio
async def test_ai_ambiguity_low_confidence_fallback():
    gst_rec = make_invoice("INV-100")
    cand1 = make_invoice("INV100")

    mock_provider = CustomAmbiguityProvider(selected_inv="INV100", confidence=0.50)

    from app.ai.gateway import ai_gateway
    orig = ai_gateway.provider
    ai_gateway.set_provider(mock_provider)

    try:
        resp = await ai_service.resolve_candidate_ambiguity_async(gst_rec, [cand1])
        assert resp.selected_candidate_invoice_number == "INV100"
        assert resp.confidence == 0.50
        assert resp.requires_manual_review is True  # Low confidence forces manual review
    finally:
        ai_gateway.set_provider(orig)


@pytest.mark.asyncio
async def test_ai_ambiguity_unlisted_candidate_rejection():
    gst_rec = make_invoice("INV-100")
    cand1 = make_invoice("INV100")

    # AI suggests an unlisted invoice number NOT in supplied candidates
    mock_provider = CustomAmbiguityProvider(selected_inv="HALLUCINATED_INV_999", confidence=0.95)

    from app.ai.gateway import ai_gateway
    orig = ai_gateway.provider
    ai_gateway.set_provider(mock_provider)

    try:
        resp = await ai_service.resolve_candidate_ambiguity_async(gst_rec, [cand1])
        assert resp.selected_candidate_invoice_number is None  # Rejected!
        assert resp.requires_manual_review is True
        assert "not in supplied ERP candidate list" in resp.reasoning
    finally:
        ai_gateway.set_provider(orig)


@pytest.mark.asyncio
async def test_ai_ambiguity_gateway_exception_fallback():
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
            raise RuntimeError("API Timeout Failure")

        async def review_discrepancy(self, request):
            pass

    from app.ai.gateway import ai_gateway
    orig = ai_gateway.provider
    ai_gateway.set_provider(ExceptionProvider())

    try:
        gst_rec = make_invoice("INV-100")
        cand1 = make_invoice("INV100")
        resp = await ai_service.resolve_candidate_ambiguity_async(gst_rec, [cand1])
        # Exception triggers fallback with manual review required
        assert resp.requires_manual_review is True
    finally:
        ai_gateway.set_provider(orig)
