import re
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from app.mapping.schemas import CanonicalInvoice, ColumnMappingConfig


class MappingService:
    """Service handling column header mapping and controlled data normalization."""

    ALIAS_DICTIONARY = {
        "gstin": [
            "gstin",
            "gstin/uin",
            "vendor gstin",
            "vendor_gstin",
            "supplier gstin",
            "supplier_gstin",
            "gstin of supplier",
            "ctin",
            "gstin_supplier",
            "vendor_gst",
            "supplier_gst",
        ],
        "invoice_number": [
            "invoice_number",
            "invoice no",
            "inv no",
            "invoice_no",
            "doc no",
            "doc_no",
            "document number",
            "bill no",
            "voucher no",
            "erp_doc_num",
            "erp_doc_no",
            "invoice number",
            "doc_num",
            "document_number",
            "document_no",
            "bill_no",
            "voucher_no",
            "doc_id",
            "voucher_number",
        ],
        "invoice_date": [
            "invoice_date",
            "invoice date",
            "inv date",
            "doc date",
            "doc_date",
            "bill date",
            "bill_date",
            "date",
            "inv_date",
            "posting_date",
            "posting date",
            "entry_date",
            "transaction_date",
            "trans_date",
        ],
        "taxable_value": [
            "taxable_value",
            "taxable value",
            "taxable val",
            "taxable amount",
            "taxable_amt",
            "assessable value",
            "taxable_val",
            "assessable_value",
        ],
        "cgst": [
            "cgst",
            "cgst amount",
            "cgst_amt",
            "central tax",
            "cgst (inr)",
            "cgst_amount",
        ],
        "sgst": [
            "sgst",
            "sgst amount",
            "sgst_amt",
            "state tax",
            "sgst (inr)",
            "utgst",
            "sgst_amount",
        ],
        "igst": [
            "igst",
            "igst amount",
            "igst_amt",
            "integrated tax",
            "igst (inr)",
            "igst_amount",
        ],
        "total_invoice_value": [
            "total_invoice_value",
            "total invoice value",
            "total value",
            "invoice value",
            "invoice amount",
            "gross value",
            "gross_val",
            "total_val",
            "invoice_amount",
            "total invoice amount",
            "gross_value",
            "total_amount",
            "total_bill_val",
            "total_bill_value",
            "bill_value",
            "bill_val",
            "net_amount",
            "net_val",
            "net_value",
        ],
    }



    def auto_detect_columns(
        self, available_columns: List[str], custom_config: Optional[ColumnMappingConfig] = None
    ) -> Dict[str, str]:
        """Auto-detect source column mappings using canonical field alias definitions."""
        mapping: Dict[str, str] = {}
        normalized_available = {col.strip().lower(): col for col in available_columns}

        # Apply custom mapping overrides first if provided
        if custom_config:
            custom_dict = custom_config.model_dump(exclude_none=True)
            for canonical_field, source_col in custom_dict.items():
                if source_col in available_columns:
                    mapping[canonical_field] = source_col

        # Auto-detect remaining fields using alias dictionary
        for canonical_field, aliases in self.ALIAS_DICTIONARY.items():
            if canonical_field in mapping:
                continue

            for alias in aliases:
                if alias in normalized_available:
                    mapping[canonical_field] = normalized_available[alias]
                    break

        return mapping

    def normalize_gstin(self, value: Any) -> str:
        """Controlled normalization for GSTIN identifiers."""
        if pd.isna(value) or value is None:
            return ""
        val_str = str(value).strip().upper()
        # Remove inner spaces or hyphens if present
        val_str = re.sub(r"[\s\-]", "", val_str)
        return val_str

    def normalize_invoice_number(self, value: Any) -> str:
        """Controlled normalization for invoice numbers.

        Strictly avoids blanket prefix stripping or mandatory zero-padding
        to preserve invoice identity (per ADR-002 and SDD 2.2).
        """
        if pd.isna(value) or value is None:
            return ""
        val_str = str(value).strip().upper()
        return val_str

    def normalize_date(self, value: Any) -> Optional[str]:
        """Parse heterogeneous date formats into ISO standard YYYY-MM-DD."""
        if pd.isna(value) or value is None or str(value).strip() == "":
            return None

        val_str = str(value).strip()
        try:
            # Check ISO format YYYY-MM-DD explicitly to prevent dayfirst ambiguity
            if re.match(r"^\d{4}-\d{2}-\d{2}$", val_str):
                dt = pd.to_datetime(val_str, format="%Y-%m-%d", errors="coerce")
            else:
                dt = pd.to_datetime(val_str, dayfirst=True, errors="coerce")

            if pd.isna(dt):
                return None
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None

    def normalize_amount(self, value: Any) -> float:
        """Sanitize and parse currency strings to float rounded to 2 decimal places."""
        if pd.isna(value) or value is None:
            return 0.0

        val_str = str(value).strip()
        if val_str == "" or val_str.lower() == "nan":
            return 0.0

        # Remove currency symbols (₹, $, INR), commas, and spaces
        cleaned = re.sub(r"[₹\$\,\s]", "", val_str, flags=re.IGNORECASE)
        # Remove any leading 'INR' or trailing 'INR'
        cleaned = re.sub(r"INR", "", cleaned, flags=re.IGNORECASE).strip()

        try:
            val_float = float(cleaned)
            from decimal import Decimal, ROUND_HALF_UP
            val_decimal = Decimal(str(val_float)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return float(val_decimal)
        except (ValueError, TypeError):
            return 0.0


    def normalize_record(
        self, record: Dict[str, Any], column_mapping: Dict[str, str]
    ) -> CanonicalInvoice:
        """Normalize a single raw record dict into a CanonicalInvoice instance."""
        get_val = lambda field: record.get(column_mapping.get(field, ""), None)

        inv_num = self.normalize_invoice_number(get_val("invoice_number"))
        gstin_val = self.normalize_gstin(get_val("gstin"))
        inv_date = self.normalize_date(get_val("invoice_date"))

        taxable = self.normalize_amount(get_val("taxable_value"))
        cgst_val = self.normalize_amount(get_val("cgst"))
        sgst_val = self.normalize_amount(get_val("sgst"))
        igst_val = self.normalize_amount(get_val("igst"))

        tot_val = get_val("total_invoice_value")
        if tot_val is not None and str(tot_val).strip() != "":
            total = self.normalize_amount(tot_val)
        else:
            # Derived total if missing
            total = round(taxable + cgst_val + sgst_val + igst_val, 2)

        return CanonicalInvoice(
            invoice_number=inv_num,
            gstin=gstin_val,
            invoice_date=inv_date,
            taxable_value=taxable,
            cgst=cgst_val,
            sgst=sgst_val,
            igst=igst_val,
            total_invoice_value=total,
            raw_data=record,
        )

    async def auto_detect_columns_with_ai(
        self,
        available_columns: List[str],
        custom_config: Optional[ColumnMappingConfig] = None,
        enable_ai: bool = True,
    ) -> Dict[str, str]:
        """Auto-detect column mappings prioritizing deterministic aliases, with AI assistance for unknown headers."""
        # Step 1: Priority 1 - Deterministic alias matching
        mapping = self.auto_detect_columns(available_columns, custom_config)

        if not enable_ai or not available_columns:
            return mapping

        # Identify unmapped canonical fields and unmapped source columns
        canonical_fields = set(self.ALIAS_DICTIONARY.keys())
        missing_canonical = canonical_fields - set(mapping.keys())

        mapped_source_cols = set(mapping.values())
        unmapped_source_cols = [col for col in available_columns if col not in mapped_source_cols]

        if not missing_canonical or not unmapped_source_cols:
            return mapping

        # Step 2: Priority 2 - AI assistance for remaining unmapped column headers
        try:
            from app.ai.gateway import ai_gateway, AISchemaMappingRequest

            request = AISchemaMappingRequest(source_columns=unmapped_source_cols, source_type="INVOICE")
            response, _ = await ai_gateway.map_schema(request)

            for suggestion in response.suggestions:
                field = suggestion.canonical_field
                src_col = suggestion.source_column
                confidence = suggestion.confidence

                # Validate AI output against canonical schema constraints
                if (
                    field
                    and field in missing_canonical
                    and src_col in unmapped_source_cols
                    and confidence >= 0.70
                ):
                    mapping[field] = src_col
                    missing_canonical.remove(field)
                    unmapped_source_cols.remove(src_col)

        except Exception:
            # Fallback gracefully to deterministic mapping if AI gateway fails or throws
            pass

        return mapping

    async def detect_column_mappings_detailed(
        self,
        available_columns: List[str],
        custom_config: Optional[ColumnMappingConfig] = None,
        enable_ai: bool = True,
    ) -> List[Dict[str, Any]]:
        """Detect column mappings and return detailed metadata for each canonical field (M7.5)."""
        # Step 1: Priority 1 - Deterministic alias matching
        det_mapping = self.auto_detect_columns(available_columns, custom_config)

        suggestions_map = {}
        for canonical_field, source_col in det_mapping.items():
            suggestions_map[canonical_field] = {
                "canonical_field": canonical_field,
                "source_column": source_col,
                "method": "DETERMINISTIC",
                "confidence": 1.0,
                "reasoning": "Header matched deterministic alias dictionary",
            }

        # Step 2: Priority 2 - AI assistance for remaining unmapped column headers
        canonical_fields = set(self.ALIAS_DICTIONARY.keys())
        missing_canonical = canonical_fields - set(det_mapping.keys())

        mapped_source_cols = set(det_mapping.values())
        unmapped_source_cols = [col for col in available_columns if col not in mapped_source_cols]

        if enable_ai and missing_canonical and unmapped_source_cols:
            try:
                from app.ai.gateway import ai_gateway, AISchemaMappingRequest

                # Never send raw row data/financials, only the unmapped source column headers
                request = AISchemaMappingRequest(source_columns=unmapped_source_cols, source_type="INVOICE")
                response, _ = await ai_gateway.map_schema(request)

                for suggestion in response.suggestions:
                    field = suggestion.canonical_field
                    src_col = suggestion.source_column
                    confidence = suggestion.confidence

                    # Validate AI output against canonical schema constraints
                    if (
                        field
                        and field in missing_canonical
                        and src_col in unmapped_source_cols
                        and confidence >= 0.70
                    ):
                        suggestions_map[field] = {
                            "canonical_field": field,
                            "source_column": src_col,
                            "method": "AI_SUGGESTED",
                            "confidence": confidence,
                            "reasoning": suggestion.reasoning or "AI suggested mapping",
                        }
                        missing_canonical.remove(field)
                        unmapped_source_cols.remove(src_col)
            except Exception:
                pass

        # Fill remaining unmapped canonical fields
        for field in missing_canonical:
            suggestions_map[field] = {
                "canonical_field": field,
                "source_column": None,
                "method": "UNMAPPED",
                "confidence": 0.0,
                "reasoning": "No matching column identified.",
            }

        # Order by standard ALIAS_DICTIONARY keys sequence
        ordered_suggestions = []
        for field in self.ALIAS_DICTIONARY.keys():
            if field in suggestions_map:
                ordered_suggestions.append(suggestions_map[field])

        return ordered_suggestions


    def normalize_dataset(
        self,
        records: List[Dict[str, Any]],
        custom_config: Optional[ColumnMappingConfig] = None,
        column_mapping_override: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[CanonicalInvoice], Dict[str, str]]:
        """Normalize a dataset list of raw record dictionaries."""
        if not records:
            return [], {}

        if column_mapping_override:
            column_mapping = column_mapping_override
        else:
            available_cols = list(records[0].keys())
            column_mapping = self.auto_detect_columns(available_cols, custom_config)

        canonical_records = [
            self.normalize_record(row, column_mapping) for row in records
        ]

        return canonical_records, column_mapping


mapping_service = MappingService()

