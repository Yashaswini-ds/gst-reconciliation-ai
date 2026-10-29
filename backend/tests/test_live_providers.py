import pytest
from unittest.mock import patch, AsyncMock

from app.ai.gateway.providers.openai_provider import OpenAIAIProvider
from app.ai.gateway.providers.gemini_provider import GeminiAIProvider
from app.ai.gateway.gateway import create_default_provider
from app.ai.gateway.schemas import AISchemaMappingRequest


def test_openai_provider_missing_key_rejection():
    with pytest.raises(ValueError, match="OpenAI API key is required"):
        OpenAIAIProvider(api_key="")


def test_gemini_provider_missing_key_rejection():
    with pytest.raises(ValueError, match="Gemini API key is required"):
        GeminiAIProvider(api_key="")


def test_gateway_provider_factory_default_fallback():
    provider = create_default_provider()
    assert provider.provider_name == "fallback"


@pytest.mark.asyncio
async def test_openai_provider_schema_mapping_mock():
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.raise_for_error = MagicMock()
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"suggestions": [{"source_column": "Custom_Header", "canonical_field": "gstin", "confidence": 0.95, "evidence": "Vendor Tax ID", "reasoning": "Matches GSTIN pattern"}]}'
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        provider = OpenAIAIProvider(api_key="sk-test-key", model_name="gpt-4o")
        req = AISchemaMappingRequest(source_columns=["Custom_Header"])
        resp = await provider.map_schema(req)

        assert len(resp.suggestions) == 1
        assert resp.suggestions[0].canonical_field == "gstin"
        assert resp.suggestions[0].confidence == 0.95


@pytest.mark.asyncio
async def test_gemini_provider_schema_mapping_mock():
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.raise_for_error = MagicMock()
    mock_response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": '{"suggestions": [{"source_column": "Tax_Val", "canonical_field": "taxable_value", "confidence": 0.90, "evidence": "Taxable Amount Header", "reasoning": "Taxable value field"}]}'
                        }
                    ]
                }
            }
        ]
    }

    with patch("httpx.AsyncClient.post", return_value=mock_response):
        provider = GeminiAIProvider(api_key="gemini-test-key", model_name="gemini-1.5-flash")
        req = AISchemaMappingRequest(source_columns=["Tax_Val"])
        resp = await provider.map_schema(req)

        assert len(resp.suggestions) == 1
        assert resp.suggestions[0].canonical_field == "taxable_value"
        assert resp.suggestions[0].confidence == 0.90


def test_gateway_gemini_missing_key_fallback():
    from app.core.config import settings
    
    with patch.object(settings, "AI_PROVIDER", "gemini"), \
         patch.object(settings, "GEMINI_API_KEY", ""):
        provider = create_default_provider()
        assert provider.provider_name == "fallback"


def test_gateway_gemini_custom_model():
    from app.core.config import settings
    
    with patch.object(settings, "AI_PROVIDER", "gemini"), \
         patch.object(settings, "GEMINI_API_KEY", "dummy-key"), \
         patch.object(settings, "GEMINI_MODEL", "gemini-2.0-pro"):
        provider = create_default_provider()
        assert provider.provider_name == "gemini"
        assert provider.model_identifier == "gemini-2.0-pro"

