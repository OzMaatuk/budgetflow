"""Tests for transaction aggregator."""
import unittest
from datetime import datetime
from decimal import Decimal

from llm.models import Transaction
from llm.aggregator import Aggregator


class TestAggregator(unittest.TestCase):
    """Test Aggregator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.aggregator = Aggregator()
    
    def test_aggregate_transactions(self):
        """Test basic aggregation."""
        transactions = [
            Transaction(
                date=datetime(2025, 5, 1),
                description="Store A",
                amount=Decimal("-100"),
                category="סופר (מזון וטואלטיקה)"
            ),
            Transaction(
                date=datetime(2025, 5, 2),
                description="Store B",
                amount=Decimal("-50"),
                category="סופר (מזון וטואלטיקה)"
            ),
            Transaction(
                date=datetime(2025, 5, 3),
                description="Gas",
                amount=Decimal("-200"),
                category="רכב (דלק, חניה)"
            ),
        ]
        
        result = self.aggregator.aggregate(transactions, "test_customer")
        
        self.assertEqual(result.month, 5)
        self.assertEqual(result.totals["סופר (מזון וטואלטיקה)"], Decimal("-150"))
        self.assertEqual(result.totals["רכב (דלק, חניה)"], Decimal("-200"))
    
    def test_infer_month_majority(self):
        """Test month inference with majority vote."""
        transactions = [
            Transaction(datetime(2025, 5, 1), "A", Decimal("-10"), "Cat1"),
            Transaction(datetime(2025, 5, 2), "B", Decimal("-10"), "Cat1"),
            Transaction(datetime(2025, 6, 1), "C", Decimal("-10"), "Cat1"),
        ]
        
        result = self.aggregator.aggregate(transactions, "test_customer")
        self.assertEqual(result.month, 5)  # Majority is May
    
    def test_empty_transactions_raises_error(self):
        """Test that empty transaction list raises error."""
        with self.assertRaises(Exception):
            self.aggregator.aggregate([], "test_customer")


if __name__ == "__main__":
    unittest.main()
