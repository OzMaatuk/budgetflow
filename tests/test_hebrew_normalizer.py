"""Tests for Hebrew text normalizer."""
import unittest

from budgetflow.pdf.hebrew_normalizer import HebrewNormalizer


class TestHebrewNormalizer(unittest.TestCase):
    """Test HebrewNormalizer functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.normalizer = HebrewNormalizer()
    
    def test_normalize_basic(self):
        """Test basic normalization."""
        text = "  שלום   עולם  "
        result = self.normalizer.normalize(text)
        
        self.assertIn("שלום", result)
        self.assertIn("עולם", result)
    
    def test_strip_artifacts(self):
        """Test artifact removal."""
        text = "עמוד 1\nתוכן חשוב\nעמוד 2\nעוד תוכן"
        result = self.normalizer.strip_artifacts(text)
        
        self.assertNotIn("עמוד", result)
        self.assertIn("תוכן חשוב", result)
    
    def test_clean_whitespace(self):
        """Test whitespace cleaning."""
        text = "שורה1\n\n\n\nשורה2"
        result = self.normalizer._clean_whitespace(text)
        
        # Should reduce multiple newlines
        self.assertNotIn("\n\n\n", result)
    
    def test_remove_repeated_lines(self):
        """Test repeated line removal."""
        text = "כותרת\nכותרת\nכותרת\nתוכן\nתוכן"
        result = self.normalizer._remove_repeated_lines(text)
        
        # Should keep only first two occurrences
        self.assertEqual(result.count("כותרת"), 2)
        self.assertEqual(result.count("תוכן"), 2)


if __name__ == "__main__":
    unittest.main()
