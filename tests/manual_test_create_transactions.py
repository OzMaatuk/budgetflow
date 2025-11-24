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
from typing import List

class TestAggregator(unittest.TestCase):
    """Test Aggregator functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.INPUT_1 = '{"transactions": [{"date": "08/10/2025", "description": "BIT", "amount": -100.0, "category": "Other"}, {"date": "05/10/2025", "description": "BIT", "amount": -20.0, "category": "Other"}, {"date": "01/10/2025", "description": "אביחי אדרי", "amount": -35.0, "category": "Other"}, {"date": "30/09/2025", "description": "מחסני השוק גבעת שמואל", "amount": -69.8, "category": "Other"}, {"date": "29/09/2025", "description": "הכל לבית ולבניין", "amount": -25.0, "category": "מוצרים לבית"}, {"date": "28/09/2025", "description": "הנקודה המומחים לאלכוהול", "amount": -170.0, "category": "בילויים"}, {"date": "26/09/2025", "description": "מעיין 2000 בע\\"מ", "amount": -253.72, "category": "Other"}, {"date": "26/09/2025", "description": "סופר שווה חריש", "amount": -36.0, "category": "סופר (מזון וטואלטיקה)"}, {"date": "25/09/2025", "description": "טאבו - משרד המשפטים - ריש", "amount": -17.0, "category": "ארנונה"}, {"date": "25/09/2025", "description": "כלי עבודה", "amount": -39.0, "category": "מוצרים לבית"}, {"date": "15/09/2025", "description": "יתרת עסקאות מצטברת", "amount": -3372.25, "category": "Other"}, {"date": "18/03/2025", "description": "מקס", "amount": -98.45, "category": "Other"}, {"date": "11/03/2025", "description": "הפניקס רכב חובה", "amount": -172.0, "category": "ביטוח רכב"}, {"date": "15/10/2025", "description": "סה\\"כ לחיוב חודשי", "amount": -1000.0, "category": "Other"}]}'
        self.INPUT_2 = '{"transactions": [{"date": "16/10/2025", "description": "הו\\"ק הלו\' רבית", "amount": -49.13, "category": "Other"}, {"date": "16/10/2025", "description": "הו\\"ק הלואה קרן", "amount": -148.88, "category": "Other"}, {"date": "06/10/2025", "description": "מינ. דמי נהול", "amount": -5.30, "category": "Other"}, {"date": "06/10/2025", "description": "עמ\'הקצאת אשראי", "amount": -7.95, "category": "Other"}, {"date": "16/09/2025", "description": "הו\\"ק הלו\' רבית", "amount": -52.41, "category": "Other"}, {"date": "16/09/2025", "description": "הו\\"ק הלואה קרן", "amount": -147.82, "category": "Other"}, {"date": "03/09/2025", "description": "מינ. דמי נהול", "amount": -5.30, "category": "Other"}, {"date": "17/08/2025", "description": "הו\\"ק הלו\' רבית", "amount": -54.03, "category": "Other"}, {"date": "17/08/2025", "description": "הו\\"ק הלואה קרן", "amount": -146.77, "category": "Other"}, {"date": "05/08/2025", "description": "מינ. דמי נהול", "amount": -5.30, "category": "Other"}]}'
        self.INPUT_3 = '{"transactions":[{"date":"27/10/2025","description":"פיגורים בהלוואות","amount":-0.10,"category":"Other"},{"date":"26/10/2025","description":"פיגור הלואה-החזרה לעוש","amount":-246.93,"category":"Other"},{"date":"24/10/2025","description":"פיגור הלואה-החזרה לעוש","amount":-500.00,"category":"Other"},{"date":"23/10/2025","description":"זיכוי - מזרחי-טפחות(י)","amount":500.00,"category":"Other"},{"date":"21/10/2025","description":"פיגור הלוואה-קיזוז","amount":-426.00,"category":"Other"},{"date":"20/10/2025","description":"ב. לאומי- קיצבת ילד(י)","amount":426.00,"category":"קצבת ילדים"},{"date":"17/10/2025","description":"פיגור הלוואה","amount":1169.51,"category":"Other"},{"date":"15/10/2025","description":"הלוואה- פרעון","amount":-1911.10,"category":"Other"},{"date":"15/10/2025","description":"טפחות - לווים (י)","amount":-2404.47,"category":"Other"},{"date":"15/10/2025","description":"טפחות - לווים (י)","amount":-4418.28,"category":"Other"},{"date":"15/10/2025","description":"ישראכרט (י)","amount":-6834.68,"category":"Other"},{"date":"15/10/2025","description":"הרשאה ישראכרט (י)","amount":-1000.00,"category":"Other"},{"date":"13/10/2025","description":"ישראכרט (י)","amount":3165.00,"category":"Other"},{"date":"12/10/2025","description":"העברה באינטרנט (י)","amount":-800.00,"category":"Other"},{"date":"10/10/2025","description":"כלל חיים/בריאות (י)","amount":-123.96,"category":"ביטוח בריאות"},{"date":"10/10/2025","description":"הרשאה ישראכרט (י)","amount":-199.08,"category":"Other"},{"date":"10/10/2025","description":"הרשאה ישראכרט (י)","amount":-668.70,"category":"Other"},{"date":"10/10/2025","description":"הרשאה ישראכרט (י)","amount":-1000.00,"category":"Other"},{"date":"10/10/2025","description":"העברה באינטרנט (י)","amount":-700.00,"category":"Other"},{"date":"09/10/2025","description":"מטרופולין תחבורה צי(י)","amount":9206.23,"category":"תחבורה ציבורית"},{"date":"03/10/2025","description":"ריבית עו\"ש","amount":2.79,"category":"Other"},{"date":"03/10/2025","description":"עיריית חריש (י)","amount":5310.92,"category":"Other"},{"date":"03/10/2025","description":"כספ.חריש 193(י","amount":-1000.00,"category":"Other"},{"date":"03/10/2025","description":"ריבית עו\"ש","amount":-77.21,"category":"Other"},{"date":"03/10/2025","description":"עמלת פעולה בערוץ ישיר","amount":-24.64,"category":"Other"},{"date":"21/09/2025","description":"ביטוח לאומי-נכויות (י)","amount":1880.00,"category":"ביטוח לאומי"},{"date":"19/09/2025","description":"העברה באינטרנט (י)","amount":-200.00,"category":"Other"},{"date":"18/09/2025","description":"פיגור הלואה-החזרה לעוש","amount":-1913.40,"category":"Other"},{"date":"17/09/2025","description":"פיגור הלוואה","amount":1911.10,"category":"Other"},{"date":"17/09/2025","description":"ב. לאומי- קיצבת ילד(י)","amount":426.00,"category":"קצבת ילדים"},{"date":"17/09/2025","description":"זיכוי - בנק לאומי (י)","amount":3300.00,"category":"Other"},{"date":"15/09/2025","description":"הלוואה- פרעון","amount":-1911.10,"category":"Other"},{"date":"15/09/2025","description":"טפחות - לווים (י)","amount":-2379.90,"category":"Other"},{"date":"15/09/2025","description":"טפחות - לווים (י)","amount":-4437.98,"category":"Other"},{"date":"15/09/2025","description":"ישראכרט (י)","amount":-8825.85,"category":"Other"},{"date":"15/09/2025","description":"הרשאה ישראכרט (י)","amount":-1000.00,"category":"Other"},{"date":"15/09/2025","description":"כלל חיים/בריאות (י)","amount":-123.13,"category":"ביטוח בריאות"},{"date":"10/09/2025","description":"הרשאה ישראכרט (י)","amount":-202.62,"category":"Other"},{"date":"10/09/2025","description":"הרשאה ישראכרט (י)","amount":-681.73,"category":"Other"},{"date":"10/09/2025","description":"הרשאה ישראכרט (י)","amount":-1000.00,"category":"Other"},{"date":"08/09/2025","description":"מטרופולין תחבורה צי(י)","amount":5288.93,"category":"תחבורה ציבורית"},{"date":"04/09/2025","description":"כספ.חריש 193(י","amount":-500.00,"category":"Other"},{"date":"01/09/2025","description":"עמלת פעולה בערוץ ישיר","amount":-31.68,"category":"Other"},{"date":"31/08/2025","description":"עיריית חריש (י)","amount":7096.13,"category":"Other"},{"date":"31/08/2025","description":"כספ.חריש 193(י","amount":-2000.00,"category":"Other"},{"date":"28/08/2025","description":"ביטוח לאומי-נכויות (י)","amount":1880.00,"category":"ביטוח לאומי"},{"date":"26/08/2025","description":"זיכוי - בנק דיסקונט(י)","amount":5400.00,"category":"Other"},{"date":"26/08/2025","description":"כספ.טבריה 062(י","amount":-600.00,"category":"Other"},{"date":"20/08/2025","description":"ב. לאומי- קיצבת ילד(י)","amount":426.00,"category":"קצבת ילדים"},{"date":"17/08/2025","description":"זיכוי מידי-לאומי (י)","amount":1000.00,"category":"Other"},{"date":"15/08/2025","description":"הלוואה- פרעון","amount":-1911.10,"category":"Other"},{"date":"15/08/2025","description":"טפחות - לווים (י)","amount":-2375.48,"category":"Other"},{"date":"15/08/2025","description":"טפחות - לווים (י)","amount":-4429.43,"category":"Other"},{"date":"15/08/2025","description":"ישראכרט (י)","amount":-7972.76,"category":"Other"},{"date":"15/08/2025","description":"הרשאה ישראכרט (י)","amount":-1000.00,"category":"Other"},{"date":"11/08/2025","description":"כספ.חריש 193(י","amount":-300.00,"category":"Other"},{"date":"10/08/2025","description":"כלל חיים/בריאות (י)","amount":-120.04,"category":"ביטוח בריאות"},{"date":"10/08/2025","description":"הרשאה ישראכרט (י)","amount":-202.66,"category":"Other"},{"date":"10/08/2025","description":"הרשאה ישראכרט (י)","amount":-681.80,"category":"Other"},{"date":"10/08/2025","description":"הרשאה ישראכרט (י)","amount":-1000.00,"category":"Other"},{"date":"08/08/2025","description":"מטרופולין תחבורה צי(י)","amount":9541.56,"category":"תחבורה ציבורית"},{"date":"05/08/2025","description":"העברה באינטרנט (י)","amount":-1000.00,"category":"Other"},{"date":"01/08/2025","description":"עמלת פעולה בערוץ ישיר","amount":-24.64,"category":"Other"},{"date":"31/07/2025","description":"עיריית חריש (י)","amount":6132.44,"category":"Other"}]}'

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
        # self.f(self.INPUT_1)
        # self.f(self.INPUT_2)
        self.f(self.INPUT_3)
    
if __name__ == "__main__":
    # Discover and run all tests
    loader = unittest.TestLoader()
    start_dir = Path(__file__).parent
    suite = loader.discover(start_dir, pattern="manual_test_create_transactions.py")
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)
