"""Transaction aggregation module."""
from decimal import Decimal
from collections import defaultdict
from typing import List, Dict
from collections import Counter

from .models import Transaction, AggregatedData
from utils.logger import get_logger
from utils.exceptions import ValidationError

logger = get_logger()


class Aggregator:
    """Aggregates transactions by category and month."""
    
    def aggregate(self, transactions: List[Transaction], customer_id: str) -> AggregatedData:
        """
        Aggregate transactions by category.
        
        Args:
            transactions: List of transactions
            customer_id: Customer identifier
            
        Returns:
            AggregatedData object
        """
        if not transactions:
            raise ValidationError("Cannot aggregate empty transaction list")
        
        # Infer month
        month = self._infer_month(transactions)
        
        # Aggregate by category
        totals = defaultdict(Decimal)
        for txn in transactions:
            totals[txn.category] += txn.amount
        
        aggregated = AggregatedData(
            customer_id=customer_id,
            month=month,
            totals=dict(totals),
            transactions=transactions
        )
        
        logger.info(
            f"Aggregated {len(transactions)} transactions into {len(totals)} categories "
            f"for month {month}"
        )
        
        return aggregated
    
    def _infer_month(self, transactions: List[Transaction]) -> int:
        """
        Infer statement month from transaction dates.
        
        Args:
            transactions: List of transactions
            
        Returns:
            Month number (1-12)
        """
        if not transactions:
            raise ValidationError("Cannot infer month from empty transaction list")
        
        # Count months
        month_counts = Counter(txn.date.month for txn in transactions)
        
        # Return most common month
        most_common_month = month_counts.most_common(1)[0][0]
        logger.debug(f"Inferred month: {most_common_month}")
        return most_common_month
