"""Enterprise Exception Hierarchy for ZERMP.

All internal errors inherit from ZERMPBaseException to ensure structured,
consistent error handling and JSON-RPC / REST response formatting.
"""

from typing import Any, Dict, Optional


class ZERMPBaseException(Exception):
    """Base exception for all domain and infrastructure errors in ZERMP."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Serialize exception to structured JSON-compatible dictionary."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(ZERMPBaseException):
    """Raised when environment variables or platform parameters are invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="CONFIG_ERROR", details=details)


class DatabaseConnectionError(ZERMPBaseException):
    """Raised when connectivity to PostgreSQL fails or times out."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="DB_CONNECTION_ERROR", details=details)


class ClickHouseExecutionError(ZERMPBaseException):
    """Raised when ClickHouse query or batch insert execution fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="CLICKHOUSE_ERROR", details=details)


class RedisLockError(ZERMPBaseException):
    """Raised when acquiring or releasing a distributed Redis lock fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="REDIS_LOCK_ERROR", details=details)


class StorageError(ZERMPBaseException):
    """Raised when S3/LocalStack object upload, download, or bucket operation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="STORAGE_ERROR", details=details)


class SFTPConnectorError(ZERMPBaseException):
    """Raised when SFTP connection, polling, or transfer operation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="SFTP_ERROR", details=details)


class ValidationError(ZERMPBaseException):
    """Raised when data ingestion records fail validation or schema rules."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message, error_code="VALIDATION_ERROR", details=details)
