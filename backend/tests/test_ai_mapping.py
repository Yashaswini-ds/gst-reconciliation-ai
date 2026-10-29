import pytest
from app.ai.gateway import (
    AIGateway,
    AISchemaMappingResponse,
    BaseAIProvider,
    ColumnMappingSuggestion,
)
from app.mapping.service import mapping_service


class CustomAISchemaProvider(BaseAIProvider):
    """Mock AI Provider returning custom schema suggestions for testing."""

    def __init__(self, suggestions):
        self._suggestions = suggestions

    @property
    def provider_name(self) -> str:
        return "custom-mock"

    @property
    def model_identifier(self) -> str:
        return "mock-v1"

    async def map_schema(self, request):
        return AISchemaMappingResponse(suggestions=self._suggestions)

    async def resolve_candidate_ambiguity(self, request):
        raise NotImplementedError()

    async def review_discrepancy(self, request):
        raise NotImplementedError()


@pytest.mark.asyncio
async def test_ai_assisted_mapping_priority():
    # "Invoice Number" matched deterministically; "Custom_Vendor_Tax_ID" handled by AI
    cols = ["Invoice Number", "Custom_Vendor_Tax_ID"]

    mock_provider = CustomAISchemaProvider(
        suggestions=[
            ColumnMappingSuggestion(
                source_column="Custom_Vendor_Tax_ID",
                canonical_field="gstin",
                confidence=0.92,
                evidence="Custom vendor tax ID header maps to gstin",
                reasoning="Custom header matching vendor GST identification number",
            )
        ]
    )

    from app.ai.gateway import ai_gateway
    original_provider = ai_gateway.provider
    ai_gateway.set_provider(mock_provider)

    try:
        mapping = await mapping_service.auto_detect_columns_with_ai(cols, enable_ai=True)
        assert mapping["invoice_number"] == "Invoice Number"  # Deterministic alias match
        assert mapping["gstin"] == "Custom_Vendor_Tax_ID"    # AI-assisted match
    finally:
        ai_gateway.set_provider(original_provider)


@pytest.mark.asyncio
async def test_ai_assisted_mapping_invalid_canonical_field():
    cols = ["Unknown_Header"]

    mock_provider = CustomAISchemaProvider(
        suggestions=[
            ColumnMappingSuggestion(
                source_column="Unknown_Header",
                canonical_field="invented_non_canonical_field",  # Invalid field not in canonical schema
                confidence=0.95,
                evidence="AI hallucinated field",
                reasoning="Invalid field name",
            )
        ]
    )

    from app.ai.gateway import ai_gateway
    original_provider = ai_gateway.provider
    ai_gateway.set_provider(mock_provider)

    try:
        mapping = await mapping_service.auto_detect_columns_with_ai(cols, enable_ai=True)
        # Invalid canonical field must be rejected
        assert "invented_non_canonical_field" not in mapping
        assert len(mapping) == 0
    finally:
        ai_gateway.set_provider(original_provider)


@pytest.mark.asyncio
async def test_ai_assisted_mapping_low_confidence():
    cols = ["Ambiguous_Header"]

    mock_provider = CustomAISchemaProvider(
        suggestions=[
            ColumnMappingSuggestion(
                source_column="Ambiguous_Header",
                canonical_field="gstin",
                confidence=0.50,  # Below 0.70 confidence threshold
                evidence="Uncertain match",
                reasoning="Low confidence",
            )
        ]
    )

    from app.ai.gateway import ai_gateway
    original_provider = ai_gateway.provider
    ai_gateway.set_provider(mock_provider)

    try:
        mapping = await mapping_service.auto_detect_columns_with_ai(cols, enable_ai=True)
        assert "gstin" not in mapping
    finally:
        ai_gateway.set_provider(original_provider)


@pytest.mark.asyncio
async def test_ai_assisted_mapping_gateway_exception():
    class ExceptionProvider(BaseAIProvider):
        @property
        def provider_name(self) -> str:
            return "exception-mock"

        @property
        def model_identifier(self) -> str:
            return "mock-v1"

        async def map_schema(self, request):
            raise RuntimeError("API Connection Failure")

        async def resolve_candidate_ambiguity(self, request):
            pass

        async def review_discrepancy(self, request):
            pass

    from app.ai.gateway import ai_gateway
    original_provider = ai_gateway.provider
    ai_gateway.set_provider(ExceptionProvider())

    try:
        cols = ["Invoice Number", "Vendor_GSTIN"]
        mapping = await mapping_service.auto_detect_columns_with_ai(cols, enable_ai=True)
        # Gateway exception handled gracefully; deterministic mappings remain intact
        assert mapping["invoice_number"] == "Invoice Number"
        assert mapping["gstin"] == "Vendor_GSTIN"
    finally:
        ai_gateway.set_provider(original_provider)


@pytest.mark.asyncio
async def test_detailed_mapping_detection():
    cols = ["Invoice Number", "Custom_Vendor_Tax_ID", "random_unmapped_column"]
    
    mock_provider = CustomAISchemaProvider(
        suggestions=[
            ColumnMappingSuggestion(
                source_column="Custom_Vendor_Tax_ID",
                canonical_field="gstin",
                confidence=0.92,
                evidence="Custom vendor tax ID header maps to gstin",
                reasoning="Custom header matching vendor GST identification number",
            )
        ]
    )

    from app.ai.gateway import ai_gateway
    original_provider = ai_gateway.provider
    ai_gateway.set_provider(mock_provider)

    try:
        detailed = await mapping_service.detect_column_mappings_detailed(cols, enable_ai=True)
        
        # Verify deterministic mapping detail
        inv_num_detail = next(d for d in detailed if d["canonical_field"] == "invoice_number")
        assert inv_num_detail["source_column"] == "Invoice Number"
        assert inv_num_detail["method"] == "DETERMINISTIC"
        assert inv_num_detail["confidence"] == 1.0

        # Verify AI suggested mapping detail
        gstin_detail = next(d for d in detailed if d["canonical_field"] == "gstin")
        assert gstin_detail["source_column"] == "Custom_Vendor_Tax_ID"
        assert gstin_detail["method"] == "AI_SUGGESTED"
        assert gstin_detail["confidence"] == 0.92

        # Verify unmapped field detail
        date_detail = next(d for d in detailed if d["canonical_field"] == "invoice_date")
        assert date_detail["source_column"] is None
        assert date_detail["method"] == "UNMAPPED"
        assert date_detail["confidence"] == 0.0

    finally:
        ai_gateway.set_provider(original_provider)


def test_user_confirmed_mapping_override():
    records = [{"Custom_Inv": "INV-001", "Supplier_Tax": "27AAAAA1111A1Z1"}]
    custom_mapping = {"invoice_number": "Custom_Inv", "gstin": "Supplier_Tax"}
    
    # Run normalize with custom mapping overrides
    canonical_records, mapping_used = mapping_service.normalize_dataset(
        records, column_mapping_override=custom_mapping
    )
    
    assert mapping_used == custom_mapping
    assert canonical_records[0].invoice_number == "INV-001"
    assert canonical_records[0].gstin == "27AAAAA1111A1Z1"
