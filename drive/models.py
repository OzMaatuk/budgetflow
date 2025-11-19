"""Data models for Drive operations."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Customer:
    """Customer information."""
    id: str  # Folder name
    folder_id: str  # Drive folder ID
    archive_folder_id: Optional[str] = None
    error_folder_id: Optional[str] = None
    duplicates_folder_id: Optional[str] = None
    report_id: Optional[str] = None  # Spreadsheet ID


@dataclass
class PDFFile:
    """PDF file information."""
    id: str  # Drive file ID
    name: str
    size: int
    created_time: datetime
    hash: Optional[str] = None
