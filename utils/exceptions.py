"""
Custom exceptions for protein evaluation service.
"""


class ProteinEvaluationError(Exception):
    """Base exception for protein evaluation errors."""
    pass


class APIError(ProteinEvaluationError):
    """Exception raised for API-related errors."""

    def __init__(self, message: str, status_code: int = None, response_text: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class UniProtAPIError(APIError):
    """Exception raised for UniProt API errors."""
    pass


class PDBAPIError(APIError):
    """Exception raised for PDB/RCSB API errors."""
    pass


class BLASTSearchError(APIError):
    """Exception raised for BLAST search errors."""
    pass


class PubMedAPIError(APIError):
    """Exception raised for PubMed API errors."""
    pass


class AIAnalysisError(ProteinEvaluationError):
    """Exception raised for AI analysis errors."""
    pass


class DatabaseError(ProteinEvaluationError):
    """Exception raised for database operation errors."""
    pass


class ValidationError(ProteinEvaluationError):
    """Exception raised for validation errors."""
    pass


class ConfigurationError(ProteinEvaluationError):
    """Exception raised for configuration errors."""
    pass


class RetryExhaustedError(APIError):
    """Exception raised when all retry attempts are exhausted."""

    def __init__(self, message: str, last_exception: Exception = None, attempts: int = 0):
        super().__init__(message)
        self.last_exception = last_exception
        self.attempts = attempts
