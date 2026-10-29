import pytest
from unittest.mock import AsyncMock, patch

from app.ai.gateway.fallback_provider import FallbackAIProvider
from app.ai.gateway.gateway import AIGateway
from app.ai.gateway.providers.gemini_provider import GeminiAIProvider
from app.ai.gateway.schemas import AIPairwiseSourceRoleRequest, AIPairwiseSourceRoleResponse
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.mark.asyncio
async def test_gemini_provider_detect_source_role_valid_assignment():
    provider = GeminiAIProvider(api_key="test-key")
    mock_payload = {
        "gst_role": "GST_LIKELY",
        "erp_role": "ERP_LIKELY",
        "assignment_valid": True,
        "confidence": 0.95,
        "reasoning": "Valid file pair assignment: GST slot contains GSTR-2B headers, ERP slot contains ERP headers."
    }

    with patch.object(provider, "_generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_payload
        request = AIPairwiseSourceRoleRequest(
            gst_columns=["GSTIN", "Invoice Number", "CGST", "SGST"],
            erp_columns=["Vendor Code", "PO Number", "Gross Amount"]
        )
        response = await provider.detect_source_role(request)

        assert isinstance(response, AIPairwiseSourceRoleResponse)
        assert response.gst_role == "GST_LIKELY"
        assert response.erp_role == "ERP_LIKELY"
        assert response.assignment_valid is True
        assert response.confidence == 0.95


@pytest.mark.asyncio
async def test_gemini_provider_detect_source_role_swapped_assignment_blocked():
    provider = GeminiAIProvider(api_key="test-key")
    mock_payload = {
        "gst_role": "ERP_LIKELY",
        "erp_role": "GST_LIKELY",
        "assignment_valid": False,
        "confidence": 0.92,
        "reasoning": "Swapped assignment: GST slot contains ERP PO numbers while ERP slot contains GSTIN."
    }

    with patch.object(provider, "_generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_payload
        request = AIPairwiseSourceRoleRequest(
            gst_columns=["Vendor Code", "PO Number"],
            erp_columns=["GSTIN", "CGST", "SGST"]
        )
        response = await provider.detect_source_role(request)

        assert response.gst_role == "ERP_LIKELY"
        assert response.erp_role == "GST_LIKELY"
        assert response.assignment_valid is False


@pytest.mark.asyncio
async def test_gemini_provider_detect_source_role_low_confidence_coerced():
    provider = GeminiAIProvider(api_key="test-key")
    mock_payload = {
        "gst_role": "GST_LIKELY",
        "erp_role": "ERP_LIKELY",
        "assignment_valid": True,
        "confidence": 0.50,
        "reasoning": "Uncertain classification."
    }

    with patch.object(provider, "_generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_payload
        request = AIPairwiseSourceRoleRequest(
            gst_columns=["Date", "Amount"],
            erp_columns=["Date", "Total"]
        )
        response = await provider.detect_source_role(request)

        assert response.gst_role == "AMBIGUOUS"
        assert response.erp_role == "AMBIGUOUS"
        assert response.assignment_valid is True


@pytest.mark.asyncio
async def test_fallback_provider_detect_source_role():
    fallback = FallbackAIProvider()
    request = AIPairwiseSourceRoleRequest(
        gst_columns=["Col1", "Col2"],
        erp_columns=["ColA", "ColB"]
    )
    response = await fallback.detect_source_role(request)

    assert isinstance(response, AIPairwiseSourceRoleResponse)
    assert response.gst_role == "AMBIGUOUS"
    assert response.erp_role == "AMBIGUOUS"
    assert response.assignment_valid is True
    assert response.confidence == 0.5


@pytest.mark.asyncio
async def test_ai_gateway_detect_source_role_fallback_on_error():
    failing_provider = GeminiAIProvider(api_key="test-key")
    with patch.object(failing_provider, "detect_source_role", side_effect=Exception("API Timeout")):
        gateway = AIGateway()
        gateway.provider = failing_provider

        request = AIPairwiseSourceRoleRequest(
            gst_columns=["Header1"],
            erp_columns=["Header2"]
        )
        response, metadata = await gateway.detect_source_role(request)

        assert response.gst_role == "AMBIGUOUS"
        assert response.assignment_valid is True
        assert metadata.fallback_used is True
        assert metadata.validation_passed is False
        assert metadata.task_type == "SOURCE_ROLE"


def test_detect_source_role_endpoint():
    mock_resp = AIPairwiseSourceRoleResponse(
        gst_role="GST_LIKELY",
        erp_role="ERP_LIKELY",
        assignment_valid=True,
        confidence=0.90,
        reasoning="Valid pairwise assignment."
    )
    with patch("app.ai.router.ai_service.detect_source_role_async", new_callable=AsyncMock) as mock_detect:
        mock_detect.return_value = mock_resp
        res = client.post(
            "/api/v1/ai/detect-source-role",
            json={
                "gst_columns": ["GSTIN", "Invoice Date", "Total Tax"],
                "erp_columns": ["Vendor Code", "Doc Date", "Gross Amount"]
            }
        )

        assert res.status_code == 200
        data = res.json()
        assert data["gst_role"] == "GST_LIKELY"
        assert data["erp_role"] == "ERP_LIKELY"
        assert data["assignment_valid"] is True
        assert data["confidence"] == 0.90
