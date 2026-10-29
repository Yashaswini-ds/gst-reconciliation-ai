from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class VendorRiskCategory(str, Enum):
    LOW_RISK = "LOW_RISK"        # Compliance Score >= 80
    MEDIUM_RISK = "MEDIUM_RISK"  # Compliance Score 50-79
    HIGH_RISK = "HIGH_RISK"      # Compliance Score < 50


class VendorRiskProfile(BaseModel):
    """Compliance risk profile for a single supplier GSTIN."""

    gstin: str = Field(..., description="15-character Supplier GSTIN")
    total_invoices: int = Field(0, description="Total invoices from this supplier")
    exact_matches: int = Field(0, description="Exact matching invoices count")
    partial_matches: int = Field(0, description="Partial matching invoices count")
    discrepancies: int = Field(0, description="Discrepant invoices count")
    unmatched: int = Field(0, description="Unmatched invoices count")
    disputed_itc_amount: float = Field(0.0, description="Total disputed / blocked ITC amount")
    claimable_itc_amount: float = Field(0.0, description="Total eligible claimable ITC amount")
    compliance_score: float = Field(100.0, ge=0.0, le=100.0, description="Vendor compliance score 0-100")
    risk_category: VendorRiskCategory = Field(VendorRiskCategory.LOW_RISK, description="Risk categorization")
    section_16_4_warning: bool = Field(False, description="True if high disputed ITC poses Section 16(4) forfeiture risk")


class VendorRiskAnalyticsReport(BaseModel):
    """Aggregate vendor compliance risk analytics report."""

    total_vendors_evaluated: int = Field(0)
    high_risk_vendors_count: int = Field(0)
    medium_risk_vendors_count: int = Field(0)
    low_risk_vendors_count: int = Field(0)
    total_disputed_itc_at_risk: float = Field(0.0)
    vendor_profiles: List[VendorRiskProfile] = Field(default=[])
