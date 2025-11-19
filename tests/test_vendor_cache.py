"""Tests for vendor cache."""
import unittest
import tempfile
import shutil
from pathlib import Path

from budgetflow.llm.vendor_cache import VendorCache


class TestVendorCache(unittest.TestCase):
    """Test VendorCache functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.cache = VendorCache()
        # Override cache directory for testing
        self.cache.cache_dir = self.test_dir
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_add_and_lookup(self):
        """Test adding and looking up vendors."""
        customer_id = "test_customer"
        vendor = "שופרסל"
        category = "סופר (מזון וטואלטיקה)"
        
        # Add mapping
        self.cache.add_mapping(customer_id, vendor, category)
        
        # Lookup should find it
        result = self.cache.lookup(customer_id, vendor)
        self.assertEqual(result, category)
    
    def test_fuzzy_match(self):
        """Test fuzzy matching."""
        customer_id = "test_customer"
        
        self.cache.add_mapping(customer_id, "שופרסל", "סופר (מזון וטואלטיקה)")
        
        # Slight typo should still match
        result = self.cache.lookup(customer_id, "שופרסאל")
        self.assertEqual(result, "סופר (מזון וטואלטיקה)")
    
    def test_customer_isolation(self):
        """Test that customers are isolated."""
        self.cache.add_mapping("customer1", "vendor1", "category1")
        
        # Different customer should not find it
        result = self.cache.lookup("customer2", "vendor1")
        self.assertIsNone(result)
    
    def test_normalize_vendor(self):
        """Test vendor normalization."""
        normalized1 = self.cache._normalize_vendor("  VENDOR  ")
        normalized2 = self.cache._normalize_vendor("vendor")
        
        self.assertEqual(normalized1, normalized2)


if __name__ == "__main__":
    unittest.main()
