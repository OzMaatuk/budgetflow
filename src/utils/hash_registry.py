# src/utils/hash_registry.py
"""File hash registry for deduplication using SQLite."""
import hashlib
import sqlite3
import os
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class FileRecord:
    # Test suite expects constructor order: customer_id, file_hash, file_name, status
    customer_id: str
    file_hash: str
    file_name: str
    status: str
    # processed_at stored as ISO string in DB; default to None and set on insert
    processed_at: Optional[datetime] = None

class HashRegistry:
    """Manages local database of processed files."""
    
    def __init__(self):
        self.db_dir = Path(os.getenv("LOCALAPPDATA")) / "BudgetFlow"
        self.db_path = self.db_dir / "budgetflow.db"
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash TEXT,
                    customer_id TEXT,
                    file_name TEXT,
                    status TEXT,
                    processed_at TEXT,
                    UNIQUE(hash, customer_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_customer ON processed_files(customer_id)")
            conn.commit()

    def is_processed(self, customer_id: str, file_hash: str) -> bool:
        """Return True if this file_hash has been processed for the given customer_id with SUCCESS status."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_files WHERE hash = ? AND customer_id = ? AND status = 'success'",
                (file_hash, customer_id)
            )
            return cursor.fetchone() is not None

    def mark_processed(self, record: FileRecord):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Ensure processed_at is stored as ISO string
            # If processed_at not provided, set to now
            if record.processed_at is None:
                record.processed_at = datetime.now()

            processed_at = (
                record.processed_at.isoformat()
                if isinstance(record.processed_at, datetime)
                else str(record.processed_at)
            )
            cursor.execute("""
                INSERT OR REPLACE INTO processed_files 
                (hash, customer_id, file_name, status, processed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                record.file_hash,
                record.customer_id,
                record.file_name,
                record.status,
                processed_at
            ))
            conn.commit()

    def clear_cache(self, customer_id: Optional[str] = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if customer_id:
                cursor.execute("DELETE FROM processed_files WHERE customer_id = ?", (customer_id,))
            else:
                cursor.execute("DELETE FROM processed_files")
            conn.commit()
            return cursor.rowcount

    def get_customer_history(self, customer_id: str) -> List[FileRecord]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 5 fields: hash, customer_id, file_name, status, processed_at
            cursor.execute(
                "SELECT hash, customer_id, file_name, status, processed_at FROM processed_files WHERE customer_id = ? ORDER BY processed_at DESC",
                (customer_id,)
            )
            rows = cursor.fetchall()
            
            results = []
            for r in rows:
                # r: (hash, customer_id, file_name, status, processed_at)
                try:
                    processed_at = datetime.fromisoformat(r[4]) if r[4] else datetime.now()
                except Exception:
                    processed_at = datetime.now()

                results.append(FileRecord(
                    customer_id=r[1],
                    file_hash=r[0],
                    file_name=r[2],
                    status=r[3],
                    processed_at=processed_at
                ))

            return results

    @staticmethod
    def calculate_hash(file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256 = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        
        return sha256.hexdigest()
