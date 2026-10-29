import difflib
import re
from typing import List, Optional, Tuple

from app.mapping.schemas import CanonicalInvoice
from app.matching.schemas import ReconciliationConfig


class CandidateGenerator:
    """Generates candidate ERP records for a GST record via exact and fuzzy matching."""

    def format_invoice_key(self, inv_num: str) -> str:
        """Helper to compute normalized key for candidate comparison (removing special chars)."""
        if not inv_num:
            return ""
        return re.sub(r"[^A-Z0-9]", "", inv_num.upper())

    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate string similarity ratio between two invoice number strings."""
        if not str1 or not str2:
            return 0.0
        
        # Compare raw normalized strings
        ratio1 = difflib.SequenceMatcher(None, str1.upper(), str2.upper()).ratio()
        
        # Compare alphanumeric-only key strings
        key1 = self.format_invoice_key(str1)
        key2 = self.format_invoice_key(str2)
        ratio2 = difflib.SequenceMatcher(None, key1, key2).ratio() if (key1 and key2) else 0.0

        return round(max(ratio1, ratio2), 3)

    def find_candidate(
        self,
        gst_record: CanonicalInvoice,
        erp_records: List[CanonicalInvoice],
        config: ReconciliationConfig,
    ) -> Tuple[Optional[CanonicalInvoice], float, str]:
        """Finds the best matching ERP candidate for a GST record.

        Returns (best_erp_candidate, confidence_score, candidate_match_type)
        """
        if not gst_record or not erp_records:
            return None, 0.0, "NO_CANDIDATE"

        gst_gstin = gst_record.gstin.strip().upper() if gst_record.gstin else ""
        gst_inv = gst_record.invoice_number.strip().upper() if gst_record.invoice_number else ""

        # Step 1: Exact candidate matching on (GSTIN + invoice_number)
        exact_matches: List[CanonicalInvoice] = []
        for erp in erp_records:
            erp_gstin = erp.gstin.strip().upper() if erp.gstin else ""
            erp_inv = erp.invoice_number.strip().upper() if erp.invoice_number else ""

            if gst_gstin and erp_gstin and gst_gstin == erp_gstin:
                if gst_inv and erp_inv and gst_inv == erp_inv:
                    exact_matches.append(erp)

        if len(exact_matches) == 1:
            return exact_matches[0], 1.0, "EXACT_ID"
        elif len(exact_matches) > 1:
            # Multiple duplicate exact candidates found in ERP dataset
            return exact_matches[0], 0.90, "EXACT_ID_DUPLICATE"

        # Step 2: Fuzzy candidate matching on invoice_number for same GSTIN
        candidate_scores: List[Tuple[CanonicalInvoice, float]] = []

        for erp in erp_records:
            erp_gstin = erp.gstin.strip().upper() if erp.gstin else ""
            if gst_gstin and erp_gstin and gst_gstin == erp_gstin:
                score = self.calculate_similarity(gst_inv, erp.invoice_number)
                if score >= config.fuzzy_threshold:
                    candidate_scores.append((erp, score))

        if candidate_scores:
            candidate_scores.sort(key=lambda x: x[1], reverse=True)
            top_score = candidate_scores[0][1]
            top_candidates = [c for c, s in candidate_scores if s == top_score]

            if len(top_candidates) > 1:
                return top_candidates[0], round(top_score * 0.9, 2), "FUZZY_ID_DUPLICATE"
            else:
                return top_candidates[0], top_score, "FUZZY_ID"


        return None, 0.0, "NO_CANDIDATE"



candidate_generator = CandidateGenerator()
