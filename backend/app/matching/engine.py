from typing import Dict, List, Optional, Set, Tuple

from app.mapping.schemas import CanonicalInvoice
from app.matching.candidate_generator import candidate_generator
from app.matching.schemas import (
    BatchReconciliationResponse,
    BatchReconciliationSummary,
    FieldDifference,
    MatchClassification,
    ReconciliationConfig,
    ReconciliationRecordResult,
    UnmatchedReason,
)


class MatchingEngine:
    """Deterministic field comparison and Reconciliation Decision Matrix engine."""

    def compare_records(
        self,
        gst_rec: CanonicalInvoice,
        erp_rec: CanonicalInvoice,
        config: ReconciliationConfig,
    ) -> Tuple[List[FieldDifference], bool, bool]:
        """Compares GST and ERP canonical records field by field.

        Returns (list_of_field_differences, has_critical_discrepancy, has_minor_difference)
        """
        differences: List[FieldDifference] = []
        has_critical_discrepancy = False
        has_minor_difference = False

        # 1. Compare Invoice Number
        if gst_rec.invoice_number != erp_rec.invoice_number:
            differences.append(
                FieldDifference(
                    field_name="invoice_number",
                    gst_value=gst_rec.invoice_number,
                    erp_value=erp_rec.invoice_number,
                    is_within_tolerance=False,
                    is_critical=False,
                )
            )
            has_minor_difference = True

        # 2. Compare GSTIN
        if gst_rec.gstin != erp_rec.gstin:
            differences.append(
                FieldDifference(
                    field_name="gstin",
                    gst_value=gst_rec.gstin,
                    erp_value=erp_rec.gstin,
                    is_within_tolerance=False,
                    is_critical=True,
                )
            )
            has_critical_discrepancy = True

        # 3. Compare Invoice Date
        if gst_rec.invoice_date != erp_rec.invoice_date:
            differences.append(
                FieldDifference(
                    field_name="invoice_date",
                    gst_value=gst_rec.invoice_date,
                    erp_value=erp_rec.invoice_date,
                    is_within_tolerance=False,
                    is_critical=False,
                )
            )
            has_minor_difference = True

        # 4. Compare Financial Numeric Fields
        numeric_fields = [
            ("taxable_value", gst_rec.taxable_value, erp_rec.taxable_value),
            ("cgst", gst_rec.cgst, erp_rec.cgst),
            ("sgst", gst_rec.sgst, erp_rec.sgst),
            ("igst", gst_rec.igst, erp_rec.igst),
            ("total_invoice_value", gst_rec.total_invoice_value, erp_rec.total_invoice_value),
        ]

        for field_name, gst_amt, erp_amt in numeric_fields:
            gst_val = float(gst_amt or 0.0)
            erp_val = float(erp_amt or 0.0)
            diff = round(abs(gst_val - erp_val), 2)

            if diff > config.amount_tolerance_inr:
                is_crit = field_name in config.critical_fields
                differences.append(
                    FieldDifference(
                        field_name=field_name,
                        gst_value=gst_val,
                        erp_value=erp_val,
                        difference_amount=diff,
                        is_within_tolerance=False,
                        is_critical=is_crit,
                    )
                )
                if is_crit:
                    has_critical_discrepancy = True
                else:
                    has_minor_difference = True

        return differences, has_critical_discrepancy, has_minor_difference

    def reconcile_batch(
        self,
        gst_records: List[CanonicalInvoice],
        erp_records: List[CanonicalInvoice],
        config: Optional[ReconciliationConfig] = None,
    ) -> BatchReconciliationResponse:
        """Executes end-to-end reconciliation over GST and ERP dataset batches."""
        if config is None:
            config = ReconciliationConfig()

        matched_erp_indices: Set[int] = set()
        results: List[ReconciliationRecordResult] = []

        exact_count = 0
        partial_count = 0
        discrepancy_count = 0
        missing_erp_count = 0
        missing_gst_count = 0
        manual_review_count = 0

        # Process each GST record
        for gst_rec in gst_records:
            erp_candidate, confidence, candidate_type = candidate_generator.find_candidate(
                gst_rec, erp_records, config
            )

            if not erp_candidate:
                # No confident candidate -> UNMATCHED (MISSING_IN_ERP)
                missing_erp_count += 1
                results.append(
                    ReconciliationRecordResult(
                        gst_record=gst_rec,
                        erp_record=None,
                        classification=MatchClassification.UNMATCHED,
                        unmatched_reason=UnmatchedReason.MISSING_IN_ERP,
                        requires_manual_review=False,
                        candidate_confidence=0.0,
                        field_differences=[],
                        remarks=["No corresponding ERP candidate identified."],
                    )
                )
                continue

            # Track candidate ERP index (prefer unconsumed index for duplicate records)
            erp_idx = next(
                (i for i, r in enumerate(erp_records) if r == erp_candidate and i not in matched_erp_indices), None
            )
            if erp_idx is None:
                erp_idx = next(
                    (i for i, r in enumerate(erp_records) if r == erp_candidate), None
                )
            if erp_idx is not None:
                matched_erp_indices.add(erp_idx)


            # Field-by-field comparison
            diffs, has_critical, has_minor = self.compare_records(gst_rec, erp_candidate, config)

            # Apply Decision Matrix Table
            if not has_critical and not has_minor:
                classification = MatchClassification.EXACT_MATCH
                exact_count += 1
            elif has_minor and not has_critical:
                classification = MatchClassification.PARTIAL_MATCH
                partial_count += 1
            else:
                classification = MatchClassification.DISCREPANCY
                discrepancy_count += 1

            # Workflow state: flag for manual review if candidate identification had ambiguity
            requires_review = candidate_type == "FUZZY_ID" or confidence < 0.95
            if requires_review:
                manual_review_count += 1

            remarks = [f"Candidate identified via {candidate_type} with confidence {confidence:.2f}."]
            if diffs:
                diff_fields = ", ".join(d.field_name for d in diffs)
                remarks.append(f"Differences found in fields: {diff_fields}.")

            results.append(
                ReconciliationRecordResult(
                    gst_record=gst_rec,
                    erp_record=erp_candidate,
                    classification=classification,
                    unmatched_reason=None,
                    requires_manual_review=requires_review,
                    candidate_confidence=confidence,
                    field_differences=diffs,
                    remarks=remarks,
                )
            )

        # Process unmatched ERP records (MISSING_IN_GST)
        for i, erp_rec in enumerate(erp_records):
            if i not in matched_erp_indices:
                missing_gst_count += 1
                results.append(
                    ReconciliationRecordResult(
                        gst_record=None,
                        erp_record=erp_rec,
                        classification=MatchClassification.UNMATCHED,
                        unmatched_reason=UnmatchedReason.MISSING_IN_GST,
                        requires_manual_review=False,
                        candidate_confidence=0.0,
                        field_differences=[],
                        remarks=["Record present in ERP, but missing in GST Portal."],
                    )
                )

        summary = BatchReconciliationSummary(
            total_gst_records=len(gst_records),
            total_erp_records=len(erp_records),
            exact_matches=exact_count,
            partial_matches=partial_count,
            discrepancies=discrepancy_count,
            unmatched_missing_in_erp=missing_erp_count,
            unmatched_missing_in_gst=missing_gst_count,
            manual_reviews_required=manual_review_count,
        )

        return BatchReconciliationResponse(
            success=True, summary=summary, results=results
        )


matching_engine = MatchingEngine()
