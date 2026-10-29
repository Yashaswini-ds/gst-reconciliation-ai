import io
import os
from typing import Tuple
import pandas as pd

from app.ingestion.exceptions import (
    EmptyFileException,
    InvalidFileTypeException,
    MalformedFileException,
    MissingEngineException,
)
from app.ingestion.schemas import FileType, IngestionMetadata, IngestionStatus


class IngestionService:
    """Service handling file ingestion, validation, and controlled pandas dataframe parsing."""

    ALLOWED_EXTENSIONS = {
        ".csv": FileType.CSV,
        ".xlsx": FileType.XLSX,
        ".xls": FileType.XLS,
    }

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal vulnerabilities."""
        return os.path.basename(filename or "uploaded_file")

    def validate_file_extension(self, filename: str) -> FileType:
        """Validate file extension against allowed formats."""
        sanitized = self.sanitize_filename(filename)
        _, ext = os.path.splitext(sanitized.lower())
        if ext not in self.ALLOWED_EXTENSIONS:
            allowed_str = ", ".join(self.ALLOWED_EXTENSIONS.keys())
            raise InvalidFileTypeException(
                f"Unsupported file extension '{ext}'. Allowed extensions are: {allowed_str}"
            )
        return self.ALLOWED_EXTENSIONS[ext]

    def ingest_file(self, filename: str, file_bytes: bytes) -> Tuple[IngestionMetadata, pd.DataFrame]:
        """Reads file bytes into a Pandas DataFrame and extracts metadata.

        Preserves original column names without normalization or schema mapping.
        """
        sanitized_filename = self.sanitize_filename(filename)
        file_type = self.validate_file_extension(sanitized_filename)

        if not file_bytes or len(file_bytes.strip()) == 0:
            raise EmptyFileException("Uploaded file is physically empty (0 bytes).")

        df = self._parse_to_dataframe(file_bytes, file_type)
        self._validate_dataframe_structure(df)

        original_columns = [str(col) for col in df.columns]

        metadata = IngestionMetadata(
            filename=sanitized_filename,
            file_type=file_type,
            row_count=len(df),
            column_count=len(original_columns),
            columns=original_columns,
            status=IngestionStatus.SUCCESS,
        )

        return metadata, df

    def _parse_to_dataframe(self, file_bytes: bytes, file_type: FileType) -> pd.DataFrame:
        """Parse raw file bytes into a pandas DataFrame based on file type."""
        buffer = io.BytesIO(file_bytes)

        if file_type == FileType.CSV:
            return self._parse_csv(buffer)
        elif file_type == FileType.XLSX:
            return self._parse_excel(buffer, engine="openpyxl", ext_name="XLSX")
        elif file_type == FileType.XLS:
            return self._parse_excel(buffer, engine="xlrd", ext_name="XLS")
        else:
            raise InvalidFileTypeException(f"Unhandled file format '{file_type}'.")

    def _parse_csv(self, buffer: io.BytesIO) -> pd.DataFrame:
        """Parse CSV with fallback encoding handling."""
        encodings_to_try = ["utf-8", "latin-1", "cp1252"]
        last_error = None

        for encoding in encodings_to_try:
            try:
                buffer.seek(0)
                df = pd.read_csv(buffer, encoding=encoding)
                return df
            except pd.errors.EmptyDataError:
                raise EmptyFileException("CSV file contains no data or headers.")
            except (pd.errors.ParserError, ValueError) as e:
                last_error = e
                continue
            except UnicodeDecodeError as e:
                last_error = e
                continue

        raise MalformedFileException(f"Failed to parse CSV file. Error: {str(last_error)}")

    def _parse_excel(self, buffer: io.BytesIO, engine: str, ext_name: str) -> pd.DataFrame:
        """Parse Excel spreadsheet with engine dependency error handling."""
        try:
            buffer.seek(0)
            df = pd.read_excel(buffer, engine=engine)
            return df
        except ImportError:
            raise MissingEngineException(
                f"Missing required parsing engine '{engine}' to process {ext_name} files."
            )
        except Exception as e:
            err_msg = str(e)
            if "No sheets" in err_msg or "Worksheet" in err_msg:
                raise EmptyFileException(f"{ext_name} file contains no readable worksheets or data.")
            raise MalformedFileException(f"Failed to parse {ext_name} file. Error: {err_msg}")

    def _validate_dataframe_structure(self, df: pd.DataFrame) -> None:
        """Validate structural sanity of loaded DataFrame."""
        if df.columns is None or len(df.columns) == 0:
            raise EmptyFileException("Uploaded file contains no usable columns.")

        if len(df) == 0:
            raise EmptyFileException("Uploaded file contains headers but zero data rows.")


ingestion_service = IngestionService()
