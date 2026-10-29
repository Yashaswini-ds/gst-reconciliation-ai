from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.ingestion.exceptions import (
    EmptyFileException,
    IngestionException,
    InvalidFileTypeException,
    MalformedFileException,
    MissingEngineException,
)
from app.ingestion.schemas import IngestionResponse
from app.ingestion.service import ingestion_service

router = APIRouter(prefix="/ingestion", tags=["Ingestion"])


@router.post(
    "/upload",
    response_model=IngestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload and ingest GST / ERP invoice file",
    description="Ingests CSV, XLSX, or XLS invoice files, validates file structure, and returns metadata with original column names preserved.",
)
async def upload_invoice_file(file: UploadFile = File(...)):
    """API endpoint to ingest an uploaded CSV or Excel file."""
    if not file or not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "MISSING_FILE", "message": "No file was uploaded or filename is empty."},
        )

    try:
        contents = await file.read()
        metadata, _ = ingestion_service.ingest_file(file.filename, contents)
        return IngestionResponse(success=True, metadata=metadata)

    except InvalidFileTypeException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message},
        )
    except EmptyFileException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        )
    except MalformedFileException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        )
    except MissingEngineException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": exc.code, "message": exc.message},
        )
    except IngestionException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code, "message": exc.message},
        )
    except Exception as exc:
        # Fallback for unexpected system errors - avoid exposing stack trace
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_INGESTION_ERROR", "message": "An unexpected error occurred during file ingestion."},
        )
