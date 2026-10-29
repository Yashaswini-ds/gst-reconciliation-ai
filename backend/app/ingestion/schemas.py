from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class IngestionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class FileType(str, Enum):
    CSV = "CSV"
    XLSX = "XLSX"
    XLS = "XLS"


class IngestionMetadata(BaseModel):
    """Metadata response describing ingested file details."""

    filename: str = Field(..., description="Original filename")
    file_type: FileType = Field(..., description="Validated file format")
    row_count: int = Field(..., ge=0, description="Total number of data rows ingested")
    column_count: int = Field(..., ge=0, description="Total number of columns ingested")
    columns: List[str] = Field(..., description="List of preserved original column names")
    status: IngestionStatus = Field(IngestionStatus.SUCCESS, description="Ingestion processing status")
    error_message: Optional[str] = Field(None, description="Detailed error description if ingestion failed")


class IngestionResponse(BaseModel):
    """API response model for file upload ingestion."""

    success: bool = True
    metadata: IngestionMetadata
