import unittest
import sys
from pathlib import Path
import json

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

import unittest
from datetime import datetime
from decimal import Decimal

from llm.models import Transaction
from llm.aggregator import Aggregator
from llm.vision_categorizer import VisionCategorizer
from typing import  List

class TestAggregator(unittest.TestCase):
    """Test Aggregator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.INPUT_1 = '{"transactions": [{"date": "08/10/2025", "description": "BIT", "amount": -100.0, "category": "Other"}, {"date": "05/10/2025", "description": "BIT", "amount": -20.0, "category": "Other"}, {"date": "01/10/2025", "description": "אביחי אדרי", "amount": -35.0, "category": "Other"}, {"date": "30/09/2025", "description": "מחסני השוק גבעת שמואל", "amount": -69.8, "category": "Other"}, {"date": "29/09/2025", "description": "הכל לבית ולבניין", "amount": -25.0, "category": "מוצרים לבית"}, {"date": "28/09/2025", "description": "הנקודה המומחים לאלכוהול", "amount": -170.0, "category": "בילויים"}, {"date": "26/09/2025", "description": "מעיין 2000 בע\\"מ", "amount": -253.72, "category": "Other"}, {"date": "26/09/2025", "description": "סופר שווה חריש", "amount": -36.0, "category": "סופר (מזון וטואלטיקה)"}, {"date": "25/09/2025", "description": "טאבו - משרד המשפטים - ריש", "amount": -17.0, "category": "ארנונה"}, {"date": "25/09/2025", "description": "כלי עבודה", "amount": -39.0, "category": "מוצרים לבית"}, {"date": "15/09/2025", "description": "יתרת עסקאות מצטברת", "amount": -3372.25, "category": "Other"}, {"date": "18/03/2025", "description": "מקס", "amount": -98.45, "category": "Other"}, {"date": "11/03/2025", "description": "הפניקס רכב חובה", "amount": -172.0, "category": "ביטוח רכב"}, {"date": "15/10/2025", "description": "סה\\"כ לחיוב חודשי", "amount": -1000.0, "category": "Other"}]}'
        self.INPUT_2 = '{"transactions": [{"date": "16/10/2025", "description": "הו\\"ק הלו\' רבית", "amount": -49.13, "category": "Other"}, {"date": "16/10/2025", "description": "הו\\"ק הלואה קרן", "amount": -148.88, "category": "Other"}, {"date": "06/10/2025", "description": "מינ. דמי נהול", "amount": -5.30, "category": "Other"}, {"date": "06/10/2025", "description": "עמ\'הקצאת אשראי", "amount": -7.95, "category": "Other"}, {"date": "16/09/2025", "description": "הו\\"ק הלו\' רבית", "amount": -52.41, "category": "Other"}, {"date": "16/09/2025", "description": "הו\\"ק הלואה קרן", "amount": -147.82, "category": "Other"}, {"date": "03/09/2025", "description": "מינ. דמי נהול", "amount": -5.30, "category": "Other"}, {"date": "17/08/2025", "description": "הו\\"ק הלו\' רבית", "amount": -54.03, "category": "Other"}, {"date": "17/08/2025", "description": "הו\\"ק הלואה קרן", "amount": -146.77, "category": "Other"}, {"date": "05/08/2025", "description": "מינ. דמי נהול", "amount": -5.30, "category": "Other"}]}'


    def f(self, input: str) -> List[Transaction]:
        ag = Aggregator()
        vc = VisionCategorizer(api_key="test_key", categories_path="resources/categories.json")

        res = vc._parse_response(input)
        print("===================================================")
        print("parsed input:")
        print(res)
        print("===================================================")
        res = vc._create_transactions(res, "test_customer")
        print("created transactions:")
        print(res)
        print("===================================================")
        print("aggregated transactions:")
        res = ag.aggregate(res, "test_customer")
        print(res)
        print("===================================================")

    def test_aggregate_transactions(self):
        self.f(self.INPUT_1)
        self.f(self.INPUT_2)
    
if __name__ == "__main__":
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern="t.py")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
