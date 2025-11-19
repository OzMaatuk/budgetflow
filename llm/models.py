"""Data models for LLM processing."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import List, Dict


@dataclass
class Transaction:
    """Transaction data."""
    date: datetime
    description: str
    amount: Decimal
    category: str
    raw_text: str = ""


@dataclass
class AggregatedData:
    """Aggregated transaction data."""
    customer_id: str
    month: int
    totals: Dict[str, Decimal]  # category -> amount
    transactions: List[Transaction]
