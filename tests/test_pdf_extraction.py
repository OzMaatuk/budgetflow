"""Test PDF extraction locally for debugging."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf.processor import PDFProcessor
from utils.logger import get_logger

def test_pdf(pdf_path: str):
    """Test PDF extraction on a specific file."""
    logger = get_logger("DEBUG")
    processor = PDFProcessor()
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"Error: File not found: {pdf_path}")
        return
    
    print(f"\n{'='*60}")
    print(f"Testing PDF: {pdf_file.name}")
    print(f"{'='*60}\n")
    
    try:
        text = processor.extract_text(pdf_file)
        print(f"\n✓ SUCCESS: Extracted {len(text)} characters")
        print(f"\nFirst 500 characters:")
        print("-" * 60)
        print(text[:500])
        print("-" * 60)
        
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        print(f"\nTrying to extract anyway to see what we get...")
        
        # Try both methods directly
        print("\n--- pdfplumber attempt ---")
        text1 = processor._extract_with_pdfplumber(pdf_file)
        if text1:
            print(f"Extracted {len(text1)} chars")
            print(text1[:200])
        else:
            print("No text extracted")
        
        print("\n--- pypdf attempt ---")
        text2 = processor._extract_with_pypdf(pdf_file)
        if text2:
            print(f"Extracted {len(text2)} chars")
            print(text2[:200])
        else:
            print("No text extracted")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_pdf_extraction.py <path_to_pdf>")
        print("\nExample:")
        print("  python test_pdf_extraction.py \"C:\\path\\to\\file.pdf\"")
        sys.exit(1)
    
    test_pdf(sys.argv[1])
