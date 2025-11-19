"""Hebrew text normalization for PDF extractions."""
import re
import unicodedata
from typing import List

from budgetflow.utils import get_logger

logger = get_logger()


class HebrewNormalizer:
    """Normalizes Hebrew text from PDF extractions."""
    
    # Common PDF artifacts to remove
    ARTIFACTS = [
        r"עמוד \d+",  # Page numbers
        r"Page \d+",
        r"דף \d+",
        r"\d+/\d+",  # Date-like patterns that are page numbers
    ]
    
    # Legal disclaimers patterns
    LEGAL_PATTERNS = [
        r"כל הזכויות שמורות.*",
        r"מסמך זה.*סודי.*",
        r"אין להעתיק.*",
    ]
    
    def normalize(self, text: str) -> str:
        """
        Normalize Hebrew text.
        
        Args:
            text: Raw extracted text
            
        Returns:
            Normalized text
        """
        if not text:
            return ""
        
        # Normalize Unicode
        text = unicodedata.normalize("NFC", text)
        
        # Detect and fix direction if needed
        if self._needs_reversal(text):
            text = self.reverse_lines(text)
        
        # Strip artifacts
        text = self.strip_artifacts(text)
        
        # Clean up whitespace
        text = self._clean_whitespace(text)
        
        logger.debug(f"Normalized text to {len(text)} characters")
        return text
    
    def _needs_reversal(self, text: str) -> bool:
        """
        Check if text needs line reversal.
        
        Args:
            text: Text to check
            
        Returns:
            True if reversal needed
        """
        # Sample first 500 chars
        sample = text[:500]
        
        # Count Hebrew characters
        hebrew_count = sum(1 for c in sample if '\u0590' <= c <= '\u05FF')
        
        # If significant Hebrew content, check for RTL markers
        if hebrew_count > 20:
            # Check for common RTL issues (numbers appearing before Hebrew text)
            # This is a heuristic - may need refinement
            lines = sample.split('\n')[:10]
            reversed_lines = sum(1 for line in lines if re.match(r'^\d+.*[\u0590-\u05FF]', line))
            
            return reversed_lines > len(lines) // 2
        
        return False
    
    def reverse_lines(self, text: str) -> str:
        """
        Reverse line direction for RTL text.
        
        Args:
            text: Text with incorrect direction
            
        Returns:
            Text with corrected direction
        """
        lines = text.split('\n')
        reversed_lines = []
        
        for line in lines:
            # Only reverse lines with Hebrew content
            if any('\u0590' <= c <= '\u05FF' for c in line):
                # Reverse the line but keep numbers in place
                reversed_line = self._reverse_rtl_line(line)
                reversed_lines.append(reversed_line)
            else:
                reversed_lines.append(line)
        
        return '\n'.join(reversed_lines)
    
    def _reverse_rtl_line(self, line: str) -> str:
        """
        Reverse a single RTL line intelligently.
        
        Args:
            line: Line to reverse
            
        Returns:
            Reversed line
        """
        # This is a simplified reversal
        # For production, consider using python-bidi library
        return line[::-1]
    
    def strip_artifacts(self, text: str) -> str:
        """
        Remove common PDF artifacts.
        
        Args:
            text: Text with artifacts
            
        Returns:
            Cleaned text
        """
        # Remove artifact patterns
        for pattern in self.ARTIFACTS:
            text = re.sub(pattern, '', text, flags=re.MULTILINE)
        
        # Remove legal disclaimers
        for pattern in self.LEGAL_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.DOTALL)
        
        # Remove repeated headers (same line appearing multiple times)
        text = self._remove_repeated_lines(text)
        
        return text
    
    def _remove_repeated_lines(self, text: str) -> str:
        """
        Remove lines that repeat more than twice.
        
        Args:
            text: Text with potential repeated lines
            
        Returns:
            Text with repeats removed
        """
        lines = text.split('\n')
        line_counts = {}
        result_lines = []
        
        for line in lines:
            stripped = line.strip()
            if not stripped:
                result_lines.append(line)
                continue
            
            count = line_counts.get(stripped, 0)
            if count < 2:  # Keep first two occurrences
                result_lines.append(line)
                line_counts[stripped] = count + 1
        
        return '\n'.join(result_lines)
    
    def _clean_whitespace(self, text: str) -> str:
        """
        Clean up excessive whitespace.
        
        Args:
            text: Text with whitespace issues
            
        Returns:
            Cleaned text
        """
        # Replace multiple spaces with single space
        text = re.sub(r' +', ' ', text)
        
        # Replace multiple newlines with double newline
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Strip leading/trailing whitespace from lines
        lines = [line.strip() for line in text.split('\n')]
        
        return '\n'.join(lines)
