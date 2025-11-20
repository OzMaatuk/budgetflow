"""Custom exception classes for BudgetFlow."""


class BudgetFlowError(Exception):
    """Base exception for BudgetFlow."""
    pass


class ConfigError(BudgetFlowError):
    """Configuration-related errors."""
    pass


class NetworkError(BudgetFlowError):
    """Network and API-related errors."""
    pass


class PDFError(BudgetFlowError):
    """PDF extraction errors."""
    pass


class LLMError(BudgetFlowError):
    """LLM processing errors."""
    pass


class SheetsError(BudgetFlowError):
    """Google Sheets errors."""
    pass


class ValidationError(BudgetFlowError):
    """Data validation errors."""
    pass


# Retryable errors
class RetryableError(BudgetFlowError):
    """Base class for errors that should trigger retry."""
    pass


class RetryableNetworkError(RetryableError, NetworkError):
    """Network errors that can be retried."""
    pass


class RetryableLLMError(RetryableError, LLMError):
    """LLM errors that can be retried."""
    pass
