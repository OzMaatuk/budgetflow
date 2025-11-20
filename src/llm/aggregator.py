"""Transaction aggregation module."""
from decimal import Decimal
from collections import defaultdict, Counter
from typing import List

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
        
        # Infer month from most common transaction month
        month_counts = Counter(txn.date.month for txn in transactions)
        month = month_counts.most_common(1)[0][0]
        
        # Aggregate by category
        totals = defaultdict(Decimal)
        for txn in transactions:
            totals[txn.category] += txn.amount
        
        logger.info(
            f"Aggregated {len(transactions)} transactions into {len(totals)} categories "
            f"for month {month}"
        )
        
        return AggregatedData(
            customer_id=customer_id,
            month=month,
            totals=dict(totals),
            transactions=transactions
        )
