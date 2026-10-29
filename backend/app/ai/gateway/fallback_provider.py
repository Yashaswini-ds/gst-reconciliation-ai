from app.ai.gateway.base_provider import BaseAIProvider
from app.ai.gateway.schemas import (
    AICandidateResolutionRequest,
    AICandidateResolutionResponse,
    AIDiscrepancyReviewRequest,
    AIDiscrepancyReviewResponse,
    AIPairwiseSourceRoleRequest,
    AIPairwiseSourceRoleResponse,
    AIResolutionRequest,
    AIResolutionResponse,
    AISchemaMappingRequest,
    AISchemaMappingResponse,
    ColumnMappingSuggestion,
)
from app.ai.schemas import (
    AccountingAdjustmentVoucher,
    ResolutionActionType,
    VendorNoticeDraft,
    VoucherType,
)
from app.mapping.service import mapping_service
from app.matching.candidate_generator import candidate_generator
from app.matching.schemas import MatchClassification


class FallbackAIProvider(BaseAIProvider):
    """Deterministic fallback AI provider used when external LLMs are disabled or unavailable."""

    @property
    def provider_name(self) -> str:
        return "fallback"

    @property
    def model_identifier(self) -> str:
        return "deterministic-rules-engine"

    async def map_schema(self, request: AISchemaMappingRequest) -> AISchemaMappingResponse:
        """Fallback schema mapping using exact alias dictionary lookups."""
        suggestions = []
        for col in request.source_columns:
            clean_col = col.strip().lower()
            found_field = None

            for field_name, aliases in mapping_service.ALIAS_DICTIONARY.items():
                if clean_col in aliases:
                    found_field = field_name
                    break

            if found_field:
                suggestions.append(
                    ColumnMappingSuggestion(
                        source_column=col,
                        canonical_field=found_field,
                        confidence=1.0,
                        evidence="Header matched deterministic alias dictionary",
                        reasoning=f"Source column '{col}' matched alias list for canonical field '{found_field}'.",
                    )
                )
            else:
                suggestions.append(
                    ColumnMappingSuggestion(
                        source_column=col,
                        canonical_field=None,
                        confidence=0.0,
                        evidence="Header not recognized in alias dictionary",
                        reasoning=f"Source column '{col}' could not be safely mapped deterministically.",
                    )
                )

        return AISchemaMappingResponse(suggestions=suggestions)

    async def resolve_candidate_ambiguity(
        self, request: AICandidateResolutionRequest
    ) -> AICandidateResolutionResponse:
        """Fallback candidate ambiguity resolution using rule-assisted candidate generator."""
        gst = request.gst_record
        candidates = request.candidate_erp_records

        if not candidates:
            return AICandidateResolutionResponse(
                selected_candidate_invoice_number=None,
                confidence=0.0,
                evidence=["No ERP candidate records supplied."],
                reasoning="Candidate list was empty.",
                requires_manual_review=True,
            )

        best_cand = None
        best_score = 0.0

        for cand in candidates:
            score = candidate_generator.calculate_similarity(
                gst.invoice_number, cand.invoice_number
            )
            if score > best_score:
                best_score = score
                best_cand = cand

        requires_review = best_score < 0.95 or len(candidates) > 1

        return AICandidateResolutionResponse(
            selected_candidate_invoice_number=best_cand.invoice_number if best_cand else None,
            confidence=best_score,
            evidence=[
                f"Evaluated {len(candidates)} candidates against GST invoice {gst.invoice_number}.",
                f"Best similarity score: {best_score:.2f}",
            ],
            reasoning=f"Selected candidate '{best_cand.invoice_number if best_cand else 'None'}' based on similarity.",
            requires_manual_review=requires_review,
        )

    async def review_discrepancy(
        self, request: AIDiscrepancyReviewRequest
    ) -> AIDiscrepancyReviewResponse:
        """Fallback discrepancy review using pre-computed deterministic FieldDifference metadata."""
        res = request.reconciliation_result
        classification = res.classification

        if classification == MatchClassification.EXACT_MATCH:
            return AIDiscrepancyReviewResponse(
                explanation="No discrepancies found. Record is an exact match.",
                ai_remark="All required fields and financial amounts satisfy configured rules and tolerances.",
                audit_remark="Verified EXACT_MATCH. Suitable for automated ITC claim processing.",
                recommended_action="Approve automatically.",
            )

        if classification == MatchClassification.UNMATCHED:
            reason_str = res.unmatched_reason.value if res.unmatched_reason else "UNMATCHED"
            return AIDiscrepancyReviewResponse(
                explanation=f"Record is unmatched ({reason_str}). No corresponding invoice candidate identified.",
                ai_remark=f"UNMATCHED: Invoice is un-reconciled due to absence of corresponding candidate record.",
                audit_remark=f"Flagged as {reason_str}. Action required before GSTR-3B filing deadline.",
                recommended_action="Contact vendor to verify invoice issuance or upload missing ERP entry.",
            )

        # For PARTIAL_MATCH and DISCREPANCY results
        diff_summaries: List[str] = []
        for diff in res.field_differences:
            if diff.difference_amount is not None:
                diff_summaries.append(
                    f"{diff.field_name}: GST={diff.gst_value} vs ERP={diff.erp_value} (diff={diff.difference_amount})"
                )
            else:
                diff_summaries.append(
                    f"{diff.field_name}: GST='{diff.gst_value}' vs ERP='{diff.erp_value}'"
                )

        diff_str = "; ".join(diff_summaries) if diff_summaries else "Minor non-critical differences observed."

        if classification == MatchClassification.PARTIAL_MATCH:
            explanation = f"Partial match identified. {diff_str}"
            ai_remark = "PARTIAL_MATCH: Transaction relationship established, but non-critical field variations exist."
            audit_remark = "PARTIAL_MATCH recorded. Total transaction value remains consistent."
            recommended_action = "Review date or minor component variations and confirm acceptance."
        else:  # DISCREPANCY
            explanation = f"Financial discrepancy detected. {diff_str}"
            ai_remark = f"DISCREPANCY: Critical financial fields exceed configured tolerance limits ({diff_str})."
            audit_remark = "DISCREPANCY flagged. Ineligible for automatic ITC claim until resolved."
            recommended_action = "Request amended debit/credit note from vendor or post correction entry in ERP."

        return AIDiscrepancyReviewResponse(
            explanation=explanation,
            ai_remark=ai_remark,
            audit_remark=audit_remark,
            recommended_action=recommended_action,
        )

    async def generate_resolution_recommendation(
        self, request: AIResolutionRequest
    ) -> AIResolutionResponse:
        """Fallback resolution recommendation engine generating accounting vouchers and vendor notices."""
        res = request.reconciliation_result
        classification = res.classification
        supplier = request.supplier_name or "Supplier"

        gst_rec = res.gst_record
        erp_rec = res.erp_record

        # 1. EXACT MATCH
        if classification == MatchClassification.EXACT_MATCH:
            return AIResolutionResponse(
                action_type=ResolutionActionType.ACCEPT_TOLERANCE_DIFFERENCE,
                summary="Transaction fully matched. No accounting entry or vendor notice required.",
                reasoning="Both GST portal record and ERP Purchase Register match deterministically.",
                adjustment_voucher=None,
                vendor_notice=None,
                confidence_score=1.0,
            )

        # 2. UNMATCHED
        if classification == MatchClassification.UNMATCHED:
            # Missing in ERP (Present in GST)
            if gst_rec and not erp_rec:
                return AIResolutionResponse(
                    action_type=ResolutionActionType.POST_JOURNAL_ADJUSTMENT,
                    summary=f"Post Purchase Register entry for Invoice #{gst_rec.invoice_number} from {gst_rec.gstin}.",
                    reasoning="Invoice reflected in GSTR-2B but omitted in ERP. Supplier filed tax, credit available under Sec 16(2)(aa).",
                    adjustment_voucher=AccountingAdjustmentVoucher(
                        voucher_type=VoucherType.JOURNAL_ENTRY,
                        debit_account="Input Tax Credit (CGST/SGST/IGST) Account",
                        credit_account=f"Vendor Payable Account ({supplier})",
                        amount=gst_rec.total_invoice_value,
                        tax_breakdown={"cgst": gst_rec.cgst, "sgst": gst_rec.sgst, "igst": gst_rec.igst},
                        narration=f"Being purchase entry recorded for GSTR-2B Inv #{gst_rec.invoice_number} dated {gst_rec.invoice_date} from {gst_rec.gstin}.",
                    ),
                    vendor_notice=None,
                    confidence_score=0.95,
                )

            # Missing in GSTR-2B (Present in ERP)
            if erp_rec and not gst_rec:
                notice_body = (
                    f"Dear {supplier} Team,\n\n"
                    f"Our records indicate Purchase Invoice #{erp_rec.invoice_number} dated {erp_rec.invoice_date} "
                    f"for total amount ₹{erp_rec.total_invoice_value:.2f} was booked in our ERP, but is NOT reflected in our GSTR-2B statement.\n\n"
                    f"Under CGST Rule 36(4) & Section 16(2)(aa), Input Tax Credit cannot be claimed until the invoice is uploaded in your GSTR-1.\n"
                    f"Please verify and include this invoice in your upcoming GSTR-1 return filing.\n\n"
                    f"Regards,\nFinance & Tax Compliance Department"
                )
                return AIResolutionResponse(
                    action_type=ResolutionActionType.HOLD_ITC_CLAIM,
                    summary=f"Hold ITC claim for Invoice #{erp_rec.invoice_number} until vendor files GSTR-1.",
                    reasoning="ITC claim blocked under Section 16(2)(aa) of CGST Act due to non-reflection in GSTR-2B.",
                    adjustment_voucher=AccountingAdjustmentVoucher(
                        voucher_type=VoucherType.JOURNAL_ENTRY,
                        debit_account="GST ITC Suspense / Blocked Credit Account",
                        credit_account="Input Tax Credit Claimable Account",
                        amount=erp_rec.total_invoice_value,
                        tax_breakdown={"cgst": erp_rec.cgst, "sgst": erp_rec.sgst, "igst": erp_rec.igst},
                        narration=f"Being ITC claim deferred for Inv #{erp_rec.invoice_number} due to non-reflection in GSTR-2B.",
                    ),
                    vendor_notice=VendorNoticeDraft(
                        subject=f"Urgent: Non-reflection of Invoice #{erp_rec.invoice_number} in GSTR-2B",
                        recipient_gstin=erp_rec.gstin,
                        recipient_name=supplier,
                        notice_body=notice_body,
                    ),
                    confidence_score=0.95,
                )

        # 3. DISCREPANCY (Value mismatch)
        if classification == MatchClassification.DISCREPANCY:
            gst_val = gst_rec.total_invoice_value if gst_rec else 0.0
            erp_val = erp_rec.total_invoice_value if erp_rec else 0.0
            diff = abs(erp_val - gst_val)
            inv_num = erp_rec.invoice_number if erp_rec else (gst_rec.invoice_number if gst_rec else "N/A")
            gstin = erp_rec.gstin if erp_rec else (gst_rec.gstin if gst_rec else "N/A")

            if erp_val > gst_val:
                # ERP excess -> Issue Debit Note to vendor or lower ITC claim
                notice_body = (
                    f"Dear {supplier} Team,\n\n"
                    f"A financial discrepancy was detected for Invoice #{inv_num}.\n"
                    f"ERP Booked Amount: ₹{erp_val:.2f}\n"
                    f"GSTR-2B Statement Amount: ₹{gst_val:.2f}\n"
                    f"Difference: ₹{diff:.2f}\n\n"
                    f"Please issue a Credit Note or file an amendment in your GSTR-1 for ₹{diff:.2f} to reconcile tax credits.\n\n"
                    f"Regards,\nFinance & Tax Compliance Department"
                )
                return AIResolutionResponse(
                    action_type=ResolutionActionType.ISSUE_DEBIT_NOTE,
                    summary=f"Issue Debit Note of ₹{diff:.2f} for Invoice #{inv_num} to align with GSTR-2B.",
                    reasoning=f"ERP booked value (₹{erp_val:.2f}) exceeds supplier GSTR-1 filing (₹{gst_val:.2f}). Debit note needed under GST Sec 34.",
                    adjustment_voucher=AccountingAdjustmentVoucher(
                        voucher_type=VoucherType.DEBIT_NOTE,
                        debit_account=f"Vendor Payable Account ({supplier})",
                        credit_account="Input Tax Credit Discrepancy Adjustment Account",
                        amount=diff,
                        tax_breakdown=None,
                        narration=f"Being Debit Note issued to {supplier} for Inv #{inv_num} due to GSTR-2B short-filing difference of ₹{diff:.2f}.",
                    ),
                    vendor_notice=VendorNoticeDraft(
                        subject=f"Discrepancy Notice: Tax Value Variance for Invoice #{inv_num}",
                        recipient_gstin=gstin,
                        recipient_name=supplier,
                        notice_body=notice_body,
                    ),
                    confidence_score=0.90,
                )
            else:
                # GST excess -> Credit Note / Supplier amendment
                return AIResolutionResponse(
                    action_type=ResolutionActionType.ISSUE_CREDIT_NOTE,
                    summary=f"Post Credit Note / Purchase Amendment of ₹{diff:.2f} for Invoice #{inv_num}.",
                    reasoning=f"GSTR-2B statement value (₹{gst_val:.2f}) exceeds ERP booked value (₹{erp_val:.2f}). Additional ITC available upon purchase register adjustment.",
                    adjustment_voucher=AccountingAdjustmentVoucher(
                        voucher_type=VoucherType.CREDIT_NOTE,
                        debit_account="Input Tax Credit Claimable Account",
                        credit_account=f"Vendor Payable Account ({supplier})",
                        amount=diff,
                        tax_breakdown=None,
                        narration=f"Being purchase value revised upwards by ₹{diff:.2f} for Inv #{inv_num} based on GSTR-2B confirmation.",
                    ),
                    vendor_notice=None,
                    confidence_score=0.90,
                )

        # 4. PARTIAL MATCH (Date or minor non-financial variation)
        inv_num = gst_rec.invoice_number if gst_rec else (erp_rec.invoice_number if erp_rec else "N/A")
        return AIResolutionResponse(
            action_type=ResolutionActionType.ACCEPT_TOLERANCE_DIFFERENCE,
            summary=f"Accept minor variance for Invoice #{inv_num} and amend ERP metadata.",
            reasoning="Total monetary value matches within configured tolerance; difference is confined to invoice date or non-monetary field.",
            adjustment_voucher=AccountingAdjustmentVoucher(
                voucher_type=VoucherType.PURCHASE_REGISTER_AMENDMENT,
                debit_account="Purchase Register Log Audit",
                credit_account="ERP Master Metadata",
                amount=0.0,
                tax_breakdown=None,
                narration=f"Being invoice metadata/date amended in ERP for invoice #{inv_num} to match GSTR-2B portal record.",
            ),
            vendor_notice=None,
            confidence_score=0.92,
        )

    async def detect_source_role(self, request: AIPairwiseSourceRoleRequest) -> AIPairwiseSourceRoleResponse:
        """Fallback provider returning conservative AMBIGUOUS pairwise role decision."""
        return AIPairwiseSourceRoleResponse(
            gst_role="AMBIGUOUS",
            erp_role="AMBIGUOUS",
            assignment_valid=True,
            confidence=0.5,
            reasoning="Fallback provider: Ambiguous pairwise role decision."
        )


