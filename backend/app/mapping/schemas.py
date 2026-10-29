from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CanonicalInvoice(BaseModel):
    """Standardized canonical model for GST and ERP invoice records."""

    invoice_number: str = Field(..., description="Normalized invoice identifier")
    gstin: str = Field(..., description="15-character GSTIN identifier")
    invoice_date: Optional[str] = Field(None, description="ISO standardized invoice date YYYY-MM-DD")
    taxable_value: float = Field(0.0, description="Base taxable amount")
    cgst: float = Field(0.0, description="Central GST tax amount")
    sgst: float = Field(0.0, description="State GST tax amount")
    igst: float = Field(0.0, description="Integrated GST tax amount")
    total_invoice_value: float = Field(0.0, description="Total gross invoice value inclusive of tax")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Original un-normalized input row data")


class ColumnMappingConfig(BaseModel):
    """Explicit mapping from source file column headers to canonical schema fields."""

    invoice_number: Optional[str] = Field(None, description="Source column name for invoice number")
    gstin: Optional[str] = Field(None, description="Source column name for GSTIN")
    invoice_date: Optional[str] = Field(None, description="Source column name for invoice date")
    taxable_value: Optional[str] = Field(None, description="Source column name for taxable value")
    cgst: Optional[str] = Field(None, description="Source column name for CGST")
    sgst: Optional[str] = Field(None, description="Source column name for SGST")
    igst: Optional[str] = Field(None, description="Source column name for IGST")
    total_invoice_value: Optional[str] = Field(None, description="Source column name for total invoice value")


class NormalizeRequest(BaseModel):
    """API request model for row normalization."""

    records: List[Dict[str, Any]] = Field(..., description="List of raw dataset row dictionaries")
    column_mapping: Optional[ColumnMappingConfig] = Field(None, description="Optional custom column mapping override")


class NormalizedDatasetResponse(BaseModel):
    """API response model for dataset normalization."""

    success: bool = True
    total_records: int = Field(..., ge=0)
    valid_records_count: int = Field(..., ge=0)
    column_mapping_used: Dict[str, str] = Field(...)
    records: List[CanonicalInvoice] = Field(...)


class ColumnMappingDetail(BaseModel):
    """Detailed metadata for a single canonical field mapping (M7.5)."""

    canonical_field: str = Field(..., description="Target canonical field name")
    source_column: Optional[str] = Field(None, description="Mapped source file column header")
    method: str = Field(..., description="Mapping method: DETERMINISTIC, AI_SUGGESTED, or UNMAPPED")
    confidence: float = Field(0.0, description="Mapping confidence score (0.0 to 1.0)")
    reasoning: str = Field(..., description="Human-readable mapping justification")


class DetectMappingRequest(BaseModel):
    """API request model to detect column mappings."""

    columns: List[str] = Field(..., description="List of available columns in the uploaded file")
    enable_ai: bool = Field(True, description="Enable AI assistance if deterministic matching is incomplete")


class DetectMappingResponse(BaseModel):
    """API response model containing detailed column mappings (M7.5)."""

    success: bool = True
    mappings: List[ColumnMappingDetail] = Field(...)
