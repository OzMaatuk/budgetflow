"""PDF text extraction with Hebrew support."""
from pathlib import Path
from typing import Optional
import pdfplumber
import pypdf

try:
    import aspose.ocr as ocr
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from utils.logger import get_logger
from utils.exceptions import PDFError

logger = get_logger()


class PDFProcessor:
    """Extracts text from PDF files."""
    
    MIN_TEXT_LENGTH = 50  # Reduced from 100 to handle shorter statements
    
    def __init__(self, enable_ocr: bool = True):
        """
        Initialize PDF processor.
        
        Args:
            enable_ocr: Whether to use OCR for scanned PDFs
        """
        self.enable_ocr = enable_ocr and OCR_AVAILABLE
        self.ocr_api = None
        
        if self.enable_ocr:
            try:
                logger.info("Initializing Aspose.OCR with Hebrew support...")
                self.ocr_api = ocr.AsposeOcr()
                logger.info("Aspose.OCR ready (Hebrew + English + 26 other languages)")
            except Exception as e:
                logger.warning(f"Failed to initialize OCR: {e}")
                self.enable_ocr = False
        elif enable_ocr:
            logger.warning("OCR requested but not available. Install: pip install aspose-ocr-python-net")
    
    def extract_text(self, pdf_path: Path) -> str:
        """
        Extract text from PDF file.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text
            
        Raises:
            PDFError: If extraction fails or text is too short
        """
        # Try pdfplumber first
        text = self._extract_with_pdfplumber(pdf_path)
        
        if not text or len(text) < self.MIN_TEXT_LENGTH:
            # Fallback to pypdf
            logger.info(f"pdfplumber extracted {len(text) if text else 0} chars, trying pypdf for {pdf_path.name}")
            text = self._extract_with_pypdf(pdf_path)
        
        # Try OCR if text extraction failed and OCR is enabled
        if (not text or len(text) < self.MIN_TEXT_LENGTH) and self.enable_ocr:
            logger.info(f"Text extraction insufficient, trying OCR for {pdf_path.name}")
            text = self._extract_with_ocr(pdf_path)
        
        # Validate extraction
        if not self.validate_extraction(text):
            ocr_msg = "" if self.enable_ocr else " OCR not enabled."
            raise PDFError(
                f"Extracted text too short ({len(text) if text else 0} chars, minimum {self.MIN_TEXT_LENGTH}). "
                f"File may be scanned or corrupted.{ocr_msg}"
            )
        
        logger.info(f"Successfully extracted {len(text)} characters from {pdf_path.name}")
        return text
    
    def validate_extraction(self, text: str) -> bool:
        """
        Validate extracted text.
        
        Args:
            text: Extracted text
            
        Returns:
            True if valid, False otherwise
        """
        return text and len(text) >= self.MIN_TEXT_LENGTH
    
    def _extract_with_pdfplumber(self, pdf_path: Path) -> Optional[str]:
        """
        Extract text using pdfplumber.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text or None if failed
        """
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text_parts = []
                logger.debug(f"pdfplumber: Processing {len(pdf.pages)} pages from {pdf_path.name}")
                for i, page in enumerate(pdf.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                        logger.debug(f"pdfplumber: Page {i} extracted {len(page_text)} chars")
                    else:
                        logger.debug(f"pdfplumber: Page {i} extracted no text")
                
                text = "\n".join(text_parts)
                logger.info(f"pdfplumber extracted {len(text)} chars from {len(pdf.pages)} pages in {pdf_path.name}")
                return text if text else None
                
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed for {pdf_path.name}: {e}")
            return None
    
    def _extract_with_pypdf(self, pdf_path: Path) -> Optional[str]:
        """
        Extract text using pypdf (fallback).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text or None if failed
        """
        try:
            with open(pdf_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                text_parts = []
                logger.debug(f"pypdf: Processing {len(reader.pages)} pages from {pdf_path.name}")
                
                for i, page in enumerate(reader.pages, 1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                        logger.debug(f"pypdf: Page {i} extracted {len(page_text)} chars")
                    else:
                        logger.debug(f"pypdf: Page {i} extracted no text")
                
                text = "\n".join(text_parts)
                logger.info(f"pypdf extracted {len(text)} chars from {len(reader.pages)} pages in {pdf_path.name}")
                return text if text else None
                
        except Exception as e:
            logger.error(f"pypdf extraction failed for {pdf_path.name}: {e}")
            return None
    
    def _extract_with_ocr(self, pdf_path: Path) -> Optional[str]:
        """
        Extract text using Aspose.OCR with Hebrew support.
        Processes PDF directly without image conversion.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Extracted text or None if failed
        """
        if not self.ocr_api:
            return None
        
        try:
            logger.info(f"OCR: Processing PDF directly: {pdf_path.name}")
            
            # Add PDF to recognition batch
            input_data = ocr.OcrInput(ocr.InputType.PDF)
            input_data.add(str(pdf_path))
            
            # Perform OCR on all pages (Aspose.OCR auto-detects language including Hebrew)
            results = self.ocr_api.recognize(input_data)
            
            if not results:
                logger.warning(f"OCR: No results returned for {pdf_path.name}")
                return None
            
            # Combine text from all pages
            text_parts = []
            for i, result in enumerate(results, 1):
                page_text = result.recognition_text
                if page_text:
                    text_parts.append(page_text)
                    logger.debug(f"OCR: Page {i} extracted {len(page_text)} chars")
                else:
                    logger.debug(f"OCR: Page {i} extracted no text")
            
            text = "\n\n".join(text_parts)
            logger.info(f"OCR extracted {len(text)} chars from {len(results)} pages in {pdf_path.name}")
            return text if text else None
            
        except Exception as e:
            logger.error(f"OCR extraction failed for {pdf_path.name}: {e}")
            return None
