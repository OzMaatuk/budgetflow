"""Tests for configuration manager."""
import unittest
import tempfile
import shutil
from pathlib import Path

from budgetflow.config import ConfigManager, Config


class TestConfigManager(unittest.TestCase):
    """Test ConfigManager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_manager = ConfigManager()
        # Override config directory for testing
        self.config_manager.config_dir = self.test_dir
        self.config_manager.config_file = self.test_dir / "config.json"
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration."""
        config = Config(
            gemini_api_key="test_key",
            service_account_path="/path/to/creds.json",
            root_folder_id="folder123",
            polling_interval_minutes=5
        )
        
        self.config_manager.save_config(config)
        loaded_config = self.config_manager.load_config()
        
        self.assertEqual(loaded_config.gemini_api_key, config.gemini_api_key)
        self.assertEqual(loaded_config.root_folder_id, config.root_folder_id)
    
    def test_validate_config_valid(self):
        """Test validation with valid config."""
        # Create temp service account file
        sa_file = self.test_dir / "creds.json"
        sa_file.write_text("{}")
        
        config = Config(
            gemini_api_key="test_key",
            service_account_path=str(sa_file),
            root_folder_id="folder123",
            polling_interval_minutes=5
        )
        
        is_valid, message = self.config_manager.validate_config(config)
        self.assertTrue(is_valid)
    
    def test_validate_config_missing_key(self):
        """Test validation with missing API key."""
        config = Config(
            gemini_api_key="",
            service_account_path="/path/to/creds.json",
            root_folder_id="folder123"
        )
        
        is_valid, message = self.config_manager.validate_config(config)
        self.assertFalse(is_valid)
        self.assertIn("API key", message)
    
    def test_encrypt_decrypt(self):
        """Test encryption and decryption."""
        original = "sensitive_data"
        encrypted = self.config_manager.encrypt_sensitive_data(original)
        decrypted = self.config_manager.decrypt_sensitive_data(encrypted)
        
        self.assertEqual(original, decrypted)
        self.assertNotEqual(original, encrypted)


if __name__ == "__main__":
    unittest.main()
