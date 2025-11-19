"""Logging infrastructure with customer context."""
import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


class CustomerContextFilter(logging.Filter):
    """Add customer context to log records."""
    
    def __init__(self):
        super().__init__()
        self.customer_id: Optional[str] = None
    
    def filter(self, record):
        """Add customer_id to record."""
        record.customer_id = self.customer_id or "system"
        return True


class BudgetFlowLogger:
    """Centralized logging manager."""
    
    def __init__(self, log_level: str = "INFO"):
        self.log_dir = Path(os.getenv("LOCALAPPDATA")) / "BudgetFlow" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / "service.log"
        self.customer_filter = CustomerContextFilter()
        
        # Configure root logger
        self.logger = logging.getLogger("budgetflow")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # File handler with rotation (30 days, 10MB per file)
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler with UTF-8 encoding
        import sys
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Force UTF-8 encoding for console on Windows
        if hasattr(sys.stdout, 'reconfigure'):
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except Exception:
                pass  # Ignore if reconfigure fails
        
        # Formatter with customer context
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [customer:%(customer_id)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add filter
        file_handler.addFilter(self.customer_filter)
        console_handler.addFilter(self.customer_filter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def set_customer_context(self, customer_id: Optional[str]):
        """Set current customer context for logging."""
        self.customer_filter.customer_id = customer_id
    
    def get_logger(self) -> logging.Logger:
        """Get the configured logger."""
        return self.logger


# Global logger instance
_logger_instance: Optional[BudgetFlowLogger] = None


def get_logger(log_level: str = "INFO") -> logging.Logger:
    """Get or create global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = BudgetFlowLogger(log_level)
    return _logger_instance.get_logger()


def set_customer_context(customer_id: Optional[str]):
    """Set customer context for logging."""
    global _logger_instance
    if _logger_instance:
        _logger_instance.set_customer_context(customer_id)
