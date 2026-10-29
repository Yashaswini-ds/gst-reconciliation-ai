import io
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.ingestion.exceptions import (
    EmptyFileException,
    InvalidFileTypeException,
    MalformedFileException,
)
from app.ingestion.schemas import FileType, IngestionStatus
from app.ingestion.service import ingestion_service
from app.main import app

client = TestClient(app)


# Helper function to generate XLSX bytes in memory
def create_sample_xlsx_bytes(data: dict) -> bytes:
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()


# 1. Valid CSV ingestion
def test_valid_csv_ingestion():
    csv_content = "gstin,invoice_no,amount\n27AAAAA0000A1Z5,INV-101,1500.50\n27BBBBB0000B1Z2,INV-102,2300.00\n"
    metadata, df = ingestion_service.ingest_file("gstr2b_sample.csv", csv_content.encode("utf-8"))

    assert metadata.filename == "gstr2b_sample.csv"
    assert metadata.file_type == FileType.CSV
    assert metadata.row_count == 2
    assert metadata.column_count == 3
    assert metadata.columns == ["gstin", "invoice_no", "amount"]
    assert metadata.status == IngestionStatus.SUCCESS
    assert len(df) == 2


# 2. Valid XLSX ingestion
def test_valid_xlsx_ingestion():
    xlsx_bytes = create_sample_xlsx_bytes({
        "ERP_Doc_Num": ["DOC101", "DOC102"],
        "Vendor_GSTIN": ["27AAAAA0000A1Z5", "27BBBBB0000B1Z2"],
        "Taxable_Value": [1000.0, 2000.0],
    })

    metadata, df = ingestion_service.ingest_file("erp_invoices.xlsx", xlsx_bytes)

    assert metadata.filename == "erp_invoices.xlsx"
    assert metadata.file_type == FileType.XLSX
    assert metadata.row_count == 2
    assert metadata.column_count == 3
    assert metadata.columns == ["ERP_Doc_Num", "Vendor_GSTIN", "Taxable_Value"]
    assert metadata.status == IngestionStatus.SUCCESS
    assert len(df) == 2


# 3. Unsupported extension rejection
def test_unsupported_extension_rejection():
    content = b'{"data": "test"}'

    with pytest.raises(InvalidFileTypeException) as exc_info:
        ingestion_service.ingest_file("data.json", content)

    assert "Unsupported file extension '.json'" in str(exc_info.value.message)


# 4. Empty file rejection (0 bytes)
def test_empty_file_rejection():
    with pytest.raises(EmptyFileException) as exc_info:
        ingestion_service.ingest_file("empty.csv", b"")

    assert "physically empty" in str(exc_info.value.message)


# 5. CSV with headers but zero data rows
def test_csv_headers_zero_data_rows():
    csv_content = "gstin,invoice_no,amount\n"

    with pytest.raises(EmptyFileException) as exc_info:
        ingestion_service.ingest_file("headers_only.csv", csv_content.encode("utf-8"))

    assert "headers but zero data rows" in str(exc_info.value.message)


# 6. CSV with different column names
def test_csv_different_column_names():
    csv_content = "Supplier_ID,Voucher_Number,Gross_Val\nSUP01,VOUCH-99,4500.00\n"

    metadata, df = ingestion_service.ingest_file("custom_columns.csv", csv_content.encode("utf-8"))

    assert metadata.columns == ["Supplier_ID", "Voucher_Number", "Gross_Val"]
    assert metadata.row_count == 1


# 7. Preservation of original column names
def test_preservation_of_original_column_names():
    csv_content = " Invoice Number ,CGST (INR),GSTIN/UIN\nINV-001,180.00,27AAAAA0000A1Z5\n"

    metadata, df = ingestion_service.ingest_file("unnormalized.csv", csv_content.encode("utf-8"))

    # Original spacing, casing, and characters must be strictly preserved
    assert metadata.columns == [" Invoice Number ", "CGST (INR)", "GSTIN/UIN"]
    assert list(df.columns) == [" Invoice Number ", "CGST (INR)", "GSTIN/UIN"]


# 8. Basic metadata correctness
def test_basic_metadata_correctness():
    csv_content = "Col1,Col2\nVal1,Val2\nVal3,Val4\nVal5,Val6\n"

    metadata, _ = ingestion_service.ingest_file("test_meta.csv", csv_content.encode("utf-8"))

    assert metadata.filename == "test_meta.csv"
    assert metadata.file_type == FileType.CSV
    assert metadata.row_count == 3
    assert metadata.column_count == 2
    assert metadata.status == IngestionStatus.SUCCESS


# 9. Malformed/unreadable input handling
def test_malformed_unreadable_input_handling():
    corrupt_xlsx = b"PK\x03\x04CorruptDataHereNotAValidZipFile"

    with pytest.raises(MalformedFileException) as exc_info:
        ingestion_service.ingest_file("corrupt.xlsx", corrupt_xlsx)

    assert "Failed to parse XLSX file" in str(exc_info.value.message)


# 10. API upload endpoint success
def test_api_upload_endpoint_success():
    csv_content = "gstin,invoice_no,total_val\n27AAAAA0000A1Z5,INV-500,12000.00\n"

    response = client.post(
        "/api/v1/ingestion/upload",
        files={"file": ("upload_test.csv", csv_content.encode("utf-8"), "text/csv")},
    )

    assert response.status_code == 200
    json_data = response.json()
    assert json_data["success"] is True
    assert json_data["metadata"]["filename"] == "upload_test.csv"
    assert json_data["metadata"]["file_type"] == "CSV"
    assert json_data["metadata"]["row_count"] == 1
    assert json_data["metadata"]["column_count"] == 3
    assert json_data["metadata"]["columns"] == ["gstin", "invoice_no", "total_val"]


# 11. API upload endpoint validation failure
def test_api_upload_endpoint_validation_failure():
    # Test unsupported file type via API
    response = client.post(
        "/api/v1/ingestion/upload",
        files={"file": ("invalid_file.txt", b"some text content", "text/plain")},
    )

    assert response.status_code == 400
    json_data = response.json()
    assert json_data["detail"]["code"] == "UNSUPPORTED_FILE_TYPE"

    # Test empty file via API
    response_empty = client.post(
        "/api/v1/ingestion/upload",
        files={"file": ("empty_file.csv", b"", "text/csv")},
    )

    assert response_empty.status_code == 422
    json_empty = response_empty.json()
    assert json_empty["detail"]["code"] == "EMPTY_FILE"
