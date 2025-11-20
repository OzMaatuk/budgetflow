"""Test PDF extraction using Vision API."""
import sys
import os
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

# Suppress Google API warnings
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'

from llm.vision_categorizer import VisionCategorizer
from utils.logger import get_logger

def test_vision_pdf(pdf_path: str, api_key: str):
    """Test Vision API extraction on a specific file."""
    logger = get_logger("DEBUG")
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"Error: File not found: {pdf_path}")
        return
    
    categories_path = Path(__file__).parent.parent / "resources" / "categories.json"
    if not categories_path.exists():
        print(f"Error: Categories file not found: {categories_path}")
        return
    
    print(f"\n{'='*60}")
    print(f"Testing Vision API on: {pdf_file.name}")
    print(f"{'='*60}\n")
    
    try:
        categorizer = VisionCategorizer(api_key, categories_path)
        
        # Extract transactions directly from PDF
        transactions = categorizer.extract_transactions_from_pdf(
            pdf_file,
            customer_id="test_customer"
        )
        
        print(f"\n✓ SUCCESS: Extracted {len(transactions)} transactions")
        print(f"\nTransactions:")
        print("-" * 60)
        
        for i, txn in enumerate(transactions, 1):
            print(f"{i}. {txn.date.strftime('%d/%m/%Y')} | {txn.description[:50]} | {txn.amount} | {txn.category}")
        
        print("-" * 60)
        
        # Check for Hebrew characters
        hebrew_count = sum(
            1 for txn in transactions 
            for char in txn.description 
            if '\u0590' <= char <= '\u05FF'
        )
        
        print(f"\n✓ Hebrew characters found: {hebrew_count}")
        
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_vision_extraction.py <path_to_pdf> <google_api_key>")
        print("\nExample:")
        print('  python test_vision_extraction.py "tests\\input_3.pdf" "your-api-key"')
        sys.exit(1)
    
    test_vision_pdf(sys.argv[1], sys.argv[2])
