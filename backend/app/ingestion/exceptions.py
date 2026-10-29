class IngestionException(Exception):
    """Base exception for file ingestion errors."""

    def __init__(self, message: str, code: str = "INGESTION_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class InvalidFileTypeException(IngestionException):
    """Raised when uploaded file extension is not supported."""

    def __init__(self, message: str):
        super().__init__(message=message, code="UNSUPPORTED_FILE_TYPE")


class EmptyFileException(IngestionException):
    """Raised when file is 0 bytes, has 0 rows, or 0 usable columns."""

    def __init__(self, message: str):
        super().__init__(message=message, code="EMPTY_FILE")


class MalformedFileException(IngestionException):
    """Raised when file cannot be parsed or is corrupted."""

    def __init__(self, message: str):
        super().__init__(message=message, code="MALFORMED_FILE")


class MissingEngineException(IngestionException):
    """Raised when required Excel parsing library is missing."""

    def __init__(self, message: str):
        super().__init__(message=message, code="MISSING_PARSER_ENGINE")
