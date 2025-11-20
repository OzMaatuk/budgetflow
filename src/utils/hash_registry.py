"""Hash registry for tracking processed files."""
import sqlite3
import hashlib
import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from .logger import get_logger

logger = get_logger()


@dataclass
class ProcessedFile:
    """Record of a processed file."""
    id: int
    customer_id: str
    file_hash: str
    file_name: str
    processed_at: datetime
    status: str  # 'success' or 'error'


class HashRegistry:
    """Manages registry of processed files to prevent duplicates."""
    
    def __init__(self):
        self.db_dir = Path(os.getenv("LOCALAPPDATA")) / "BudgetFlow"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.db_dir / "registry.db"
        self._init_database()
    
    def _init_database(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT CHECK(status IN ('success', 'error')) NOT NULL,
                    UNIQUE(customer_id, file_hash)
                )
            """)
            
            # Create index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_customer_hash 
                ON processed_files(customer_id, file_hash)
            """)
            
            conn.commit()
            logger.debug("Hash registry database initialized")
    
    def is_processed(self, customer_id: str, file_hash: str) -> bool:
        """Check if file has been processed."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM processed_files WHERE customer_id = ? AND file_hash = ?",
                (customer_id, file_hash)
            )
            count = cursor.fetchone()[0]
            return count > 0
    
    def mark_processed(
        self,
        customer_id: str,
        file_hash: str,
        file_name: str,
        status: str
    ) -> None:
        """Mark file as processed."""
        if status not in ('success', 'error'):
            raise ValueError(f"Invalid status: {status}")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Use Python's datetime for microsecond precision
                timestamp = datetime.now().isoformat()
                cursor.execute(
                    """
                    INSERT INTO processed_files (customer_id, file_hash, file_name, status, processed_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (customer_id, file_hash, file_name, status, timestamp)
                )
                conn.commit()
                logger.debug(f"Marked file as {status}: {file_name} (hash: {file_hash[:8]}...)")
        except sqlite3.IntegrityError:
            logger.warning(f"File already in registry: {file_name}")
    
    def get_customer_history(self, customer_id: str) -> List[ProcessedFile]:
        """Get processing history for a customer."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, customer_id, file_hash, file_name, processed_at, status
                FROM processed_files
                WHERE customer_id = ?
                ORDER BY processed_at DESC
                """,
                (customer_id,)
            )
            
            rows = cursor.fetchall()
            return [
                ProcessedFile(
                    id=row["id"],
                    customer_id=row["customer_id"],
                    file_hash=row["file_hash"],
                    file_name=row["file_name"],
                    processed_at=datetime.fromisoformat(row["processed_at"]),
                    status=row["status"]
                )
                for row in rows
            ]
    
    def clear_cache(self, customer_id: Optional[str] = None) -> int:
        """
        Clear processing cache.
        
        Args:
            customer_id: If provided, clear only for this customer. Otherwise clear all.
            
        Returns:
            Number of records deleted
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            if customer_id:
                cursor.execute("DELETE FROM processed_files WHERE customer_id = ?", (customer_id,))
                logger.info(f"Cleared cache for customer: {customer_id}")
            else:
                cursor.execute("DELETE FROM processed_files")
                logger.info("Cleared all cache")
            
            deleted = cursor.rowcount
            conn.commit()
            return deleted
    
    @staticmethod
    def calculate_hash(file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        
        return sha256.hexdigest()
