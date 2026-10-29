import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mapping.schemas import ColumnMappingConfig
from app.mapping.service import mapping_service

client = TestClient(app)


# 1. Test auto-detection of column header aliases
def test_auto_detect_columns():
    headers = ["Vendor GSTIN", "Inv No", "Bill Date", "Taxable Val", "CGST (INR)", "SGST (INR)", "IGST (INR)", "Total Value"]
    detected = mapping_service.auto_detect_columns(headers)

    assert detected["gstin"] == "Vendor GSTIN"
    assert detected["invoice_number"] == "Inv No"
    assert detected["invoice_date"] == "Bill Date"
    assert detected["taxable_value"] == "Taxable Val"
    assert detected["cgst"] == "CGST (INR)"
    assert detected["sgst"] == "SGST (INR)"
    assert detected["igst"] == "IGST (INR)"
    assert detected["total_invoice_value"] == "Total Value"


# 2. Test custom column mapping overrides
def test_custom_column_mapping_override():
    headers = ["Custom_Tax_ID", "Doc_Ref"]
    custom_cfg = ColumnMappingConfig(gstin="Custom_Tax_ID", invoice_number="Doc_Ref")
    detected = mapping_service.auto_detect_columns(headers, custom_config=custom_cfg)

    assert detected["gstin"] == "Custom_Tax_ID"
    assert detected["invoice_number"] == "Doc_Ref"


# 3. Test GSTIN normalization
def test_gstin_normalization():
    assert mapping_service.normalize_gstin(" 27aaaaa0000a1z5 ") == "27AAAAA0000A1Z5"
    assert mapping_service.normalize_gstin("27AAAAA-0000A-1Z5") == "27AAAAA0000A1Z5"
    assert mapping_service.normalize_gstin(None) == ""


# 4. Test identity-preserving invoice number normalization
def test_invoice_number_normalization():
    # Must preserve underlying invoice prefixes without blanket stripping or zero padding
    assert mapping_service.normalize_invoice_number("  inv-2024-001  ") == "INV-2024-001"
    assert mapping_service.normalize_invoice_number("ABC/1234/23-24") == "ABC/1234/23-24"
    assert mapping_service.normalize_invoice_number(None) == ""


# 5. Test heterogeneous date format parsing
def test_date_format_normalization():
    assert mapping_service.normalize_date("31/12/2023") == "2023-12-31"
    assert mapping_service.normalize_date("2023-12-31") == "2023-12-31"
    assert mapping_service.normalize_date("15-Jan-2024") == "2024-01-15"
    assert mapping_service.normalize_date("invalid date") is None
    assert mapping_service.normalize_date(None) is None


# 6. Test currency string and amount sanitization
def test_amount_normalization():
    assert mapping_service.normalize_amount(" ₹ 1,500.50 ") == 1500.50
    assert mapping_service.normalize_amount("15,000 INR") == 15000.00
    assert mapping_service.normalize_amount("$ 250.755") == 250.76
    assert mapping_service.normalize_amount(None) == 0.0
    assert mapping_service.normalize_amount("") == 0.0


# 7. Test end-to-end dataset normalization
def test_dataset_normalization():
    raw_records = [
        {
            "CTIN": "27AAAAA0000A1Z5",
            "Bill No": "  inv-999  ",
            "Date": "01/04/2024",
            "Taxable Amount": " ₹ 10,000.00 ",
            "CGST": "900",
            "SGST": "900",
            "IGST": "0",
            "Invoice Amount": "11800.00",
        }
    ]

    canonical_records, mapping_used = mapping_service.normalize_dataset(raw_records)

    assert mapping_used["gstin"] == "CTIN"
    assert mapping_used["invoice_number"] == "Bill No"
    assert len(canonical_records) == 1

    rec = canonical_records[0]
    assert rec.gstin == "27AAAAA0000A1Z5"
    assert rec.invoice_number == "INV-999"
    assert rec.invoice_date == "2024-04-01"
    assert rec.taxable_value == 10000.00
    assert rec.cgst == 900.00
    assert rec.sgst == 900.00
    assert rec.igst == 0.00
    assert rec.total_invoice_value == 11800.00


# 8. Test API endpoint POST /api/v1/mapping/normalize success
def test_api_normalize_endpoint_success():
    payload = {
        "records": [
            {
                "gstin": "27BBBBB0000B1Z2",
                "invoice_no": "INV-777",
                "invoice_date": "2024-05-10",
                "taxable_value": "5000.00",
                "total_invoice_value": "5900.00",
            }
        ]
    }

    response = client.post("/api/v1/mapping/normalize", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert data["total_records"] == 1
    assert data["valid_records_count"] == 1
    assert data["records"][0]["gstin"] == "27BBBBB0000B1Z2"
    assert data["records"][0]["invoice_number"] == "INV-777"
    assert data["records"][0]["invoice_date"] == "2024-05-10"


# 9. Test API endpoint empty records error
def test_api_normalize_endpoint_empty_records():
    payload = {"records": []}
    response = client.post("/api/v1/mapping/normalize", json=payload)

    assert response.status_code == 400
    data = response.json()
    assert data["detail"]["code"] == "EMPTY_RECORDS"
