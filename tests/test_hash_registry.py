"""Tests for hash registry."""
import unittest
import tempfile
import shutil
from pathlib import Path

from utils.hash_registry import HashRegistry


class TestHashRegistry(unittest.TestCase):
    """Test HashRegistry functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.registry = HashRegistry()
        # Override database path for testing
        self.registry.db_path = self.test_dir / "test_registry.db"
        self.registry._init_database()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_mark_and_check_processed(self):
        """Test marking and checking processed files."""
        customer_id = "test_customer"
        file_hash = "abc123"
        file_name = "test.pdf"
        
        # Initially not processed
        self.assertFalse(self.registry.is_processed(customer_id, file_hash))
        
        # Mark as processed
        self.registry.mark_processed(customer_id, file_hash, file_name, "success")
        
        # Now should be processed
        self.assertTrue(self.registry.is_processed(customer_id, file_hash))
    
    def test_customer_isolation(self):
        """Test that customers are isolated."""
        file_hash = "abc123"
        
        self.registry.mark_processed("customer1", file_hash, "test.pdf", "success")
        
        # Same hash for different customer should not be processed
        self.assertFalse(self.registry.is_processed("customer2", file_hash))
    
    def test_get_customer_history(self):
        """Test retrieving customer history."""
        customer_id = "test_customer"
        
        self.registry.mark_processed(customer_id, "hash1", "file1.pdf", "success")
        self.registry.mark_processed(customer_id, "hash2", "file2.pdf", "error")
        
        history = self.registry.get_customer_history(customer_id)
        
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].file_name, "file2.pdf")  # Most recent first
        self.assertEqual(history[1].file_name, "file1.pdf")
    
    def test_calculate_hash(self):
        """Test hash calculation."""
        # Create temp file
        test_file = self.test_dir / "test.txt"
        test_file.write_text("test content")
        
        hash1 = self.registry.calculate_hash(test_file)
        hash2 = self.registry.calculate_hash(test_file)
        
        # Same file should produce same hash
        self.assertEqual(hash1, hash2)
        
        # Different content should produce different hash
        test_file.write_text("different content")
        hash3 = self.registry.calculate_hash(test_file)
        self.assertNotEqual(hash1, hash3)


if __name__ == "__main__":
    unittest.main()
