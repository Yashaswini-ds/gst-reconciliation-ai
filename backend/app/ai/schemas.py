from typing import List, Optional
from pydantic import BaseModel, Field

from app.mapping.schemas import CanonicalInvoice
from app.matching.schemas import ReconciliationRecordResult


class AICandidateResolutionRequest(BaseModel):
    """API payload model for AI candidate ambiguity resolution."""

    gst_record: CanonicalInvoice = Field(..., description="GST Portal canonical invoice record")
    candidate_erp_records: List[CanonicalInvoice] = Field(..., description="List of ambiguous candidate ERP records")


class AIPairwiseSourceRoleRequest(BaseModel):
    """API payload model for pairwise AI file source role detection."""

    gst_columns: List[str] = Field(..., description="List of column headers from the GST input file")
    erp_columns: List[str] = Field(..., description="List of column headers from the ERP input file")


class AIPairwiseSourceRoleResponse(BaseModel):
    """Structured response contract for pairwise file source role classification."""

    gst_role: str = Field(..., description="Detected GST input role: GST_LIKELY, ERP_LIKELY, or AMBIGUOUS")
    erp_role: str = Field(..., description="Detected ERP input role: GST_LIKELY, ERP_LIKELY, or AMBIGUOUS")
    assignment_valid: bool = Field(True, description="False if an obvious role swap is detected")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence rating of role detection")
    reasoning: str = Field(..., description="Brief semantic reasoning for pairwise classification")


class AICandidateResolutionResponse(BaseModel):
    """Structured response contract returned by AI ambiguity resolution."""

    selected_candidate_invoice_number: Optional[str] = Field(None, description="Recommended ERP candidate invoice number")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI similarity and confidence score")
    evidence: List[str] = Field(default=[], description="Structured field evidence supporting the selection")
    reasoning: str = Field(..., description="Detailed reasoning explaining candidate selection")
    requires_manual_review: bool = Field(False, description="True if AI confidence is low (< 0.80)")


class AIDiscrepancyReviewRequest(BaseModel):
    """API payload model for post-reconciliation discrepancy review."""

    reconciliation_result: ReconciliationRecordResult = Field(..., description="Deterministic reconciliation result")


class AIDiscrepancyReviewResponse(BaseModel):
    """Structured response contract returned by AI post-reconciliation discrepancy review."""

    explanation: str = Field(..., description="Human-readable explanation of differences")
    ai_remark: str = Field(..., description="Summary AI analytical remark")
    audit_remark: str = Field(..., description="Formal audit remark for compliance records")
    recommended_action: str = Field(..., description="Recommended resolution action for tax team")


class ResolutionActionType(str):
    """Enum types for recommended resolution actions under GST rules."""
    ISSUE_DEBIT_NOTE = "ISSUE_DEBIT_NOTE"
    ISSUE_CREDIT_NOTE = "ISSUE_CREDIT_NOTE"
    POST_JOURNAL_ADJUSTMENT = "POST_JOURNAL_ADJUSTMENT"
    CONTACT_VENDOR = "CONTACT_VENDOR"
    ACCEPT_TOLERANCE_DIFFERENCE = "ACCEPT_TOLERANCE_DIFFERENCE"
    HOLD_ITC_CLAIM = "HOLD_ITC_CLAIM"


class VoucherType(str):
    """Enum types for standard accounting adjustment vouchers."""
    JOURNAL_ENTRY = "JOURNAL_ENTRY"
    DEBIT_NOTE = "DEBIT_NOTE"
    CREDIT_NOTE = "CREDIT_NOTE"
    PURCHASE_REGISTER_AMENDMENT = "PURCHASE_REGISTER_AMENDMENT"
    SUPPLIER_REASONING_NOTICE = "SUPPLIER_REASONING_NOTICE"


class AccountingAdjustmentVoucher(BaseModel):
    """Structured Tally / ERP ledger adjustment entry recommendation."""

    voucher_type: str = Field(..., description="Type of accounting voucher (DEBIT_NOTE | CREDIT_NOTE | JOURNAL_ENTRY)")
    debit_account: str = Field(..., description="Account head to debit (e.g. Input CGST/SGST, Vendor Payable)")
    credit_account: str = Field(..., description="Account head to credit (e.g. GST Suspense Account, Vendor Account)")
    amount: float = Field(..., description="Financial adjustment value")
    tax_breakdown: Optional[dict] = Field(default=None, description="Detailed CGST, SGST, IGST component breakdown")
    narration: str = Field(..., description="Standardized accounting ledger narration for Tally/SAP entry")


class VendorNoticeDraft(BaseModel):
    """Formal compliance email/letter draft to supplier regarding tax mismatch or missing filing."""

    subject: str = Field(..., description="Subject line for email / formal notice")
    recipient_gstin: str = Field(..., description="Supplier GSTIN")
    recipient_name: str = Field(..., description="Supplier legal/trade name")
    notice_body: str = Field(..., description="Full text of notice citing GST legal provisions")


class AIResolutionRequest(BaseModel):
    """API payload requesting AI accounting resolution & voucher generation."""

    reconciliation_result: ReconciliationRecordResult = Field(..., description="Reconciliation record result")
    supplier_name: Optional[str] = Field(None, description="Optional supplier trade name")


class AIResolutionResponse(BaseModel):
    """Structured response for AI-generated resolution action, accounting voucher, and vendor notice."""

    action_type: str = Field(..., description="Recommended action type (ISSUE_DEBIT_NOTE | HOLD_ITC_CLAIM | etc.)")
    summary: str = Field(..., description="Concise summary of recommended resolution action")
    reasoning: str = Field(..., description="GST compliance and legal rationale under Indian GST framework")
    adjustment_voucher: Optional[AccountingAdjustmentVoucher] = Field(None, description="Accounting ledger entry voucher")
    vendor_notice: Optional[VendorNoticeDraft] = Field(None, description="Draft notice to be sent to vendor")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence rating of resolution")

