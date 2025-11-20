"""Configuration manager with Windows DPAPI encryption."""
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import win32crypt


@dataclass
class Config:
    """System configuration."""
    gemini_api_key: str
    root_folder_id: str
    polling_interval_minutes: int = 5
    log_level: str = "INFO"
    max_concurrent_customers: int = 3
    # Authentication: use either service account OR OAuth
    service_account_path: Optional[str] = None
    oauth_client_secrets: Optional[str] = None
    oauth_token_path: Optional[str] = None


class ConfigManager:
    """Manages system configuration with encryption."""
    
    def __init__(self):
        self.config_dir = Path(os.getenv("LOCALAPPDATA")) / "BudgetFlow"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def load_config(self) -> Optional[Config]:
        """Load configuration from encrypted file."""
        if not self.config_file.exists():
            return None
        
        try:
            with open(self.config_file, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = win32crypt.CryptUnprotectData(encrypted_data, None, None, None, 0)[1]
            config_dict = json.loads(decrypted_data.decode("utf-8"))
            return Config(**config_dict)
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")
    
    def save_config(self, config: Config) -> None:
        """Save configuration with encryption."""
        try:
            config_json = json.dumps(asdict(config), indent=2)
            encrypted_data = win32crypt.CryptProtectData(
                config_json.encode("utf-8"),
                "BudgetFlow Configuration",
                None,
                None,
                None,
                0
            )
            
            with open(self.config_file, "wb") as f:
                f.write(encrypted_data)
        except Exception as e:
            raise RuntimeError(f"Failed to save configuration: {e}")
    
    def validate_config(self, config: Config) -> tuple[bool, str]:
        """Validate configuration values."""
        if not config.gemini_api_key:
            return False, "Gemini API key is required"
        
        # Check authentication method
        has_service_account = config.service_account_path and Path(config.service_account_path).exists()
        has_oauth = config.oauth_client_secrets and Path(config.oauth_client_secrets).exists()
        
        if not has_service_account and not has_oauth:
            return False, "Either service account or OAuth client secrets is required"
        
        if not config.root_folder_id:
            return False, "Root folder ID is required"
        
        if config.polling_interval_minutes < 1:
            return False, "Polling interval must be at least 1 minute"
        
        if config.max_concurrent_customers < 1:
            return False, "Max concurrent customers must be at least 1"
        
        return True, "Configuration is valid"
    
    def encrypt_sensitive_data(self, data: str) -> bytes:
        """Encrypt sensitive data using Windows DPAPI."""
        return win32crypt.CryptProtectData(
            data.encode("utf-8"),
            "BudgetFlow Sensitive Data",
            None,
            None,
            None,
            0
        )
    
    def decrypt_sensitive_data(self, encrypted_data: bytes) -> str:
        """Decrypt sensitive data using Windows DPAPI."""
        return win32crypt.CryptUnprotectData(encrypted_data, None, None, None, 0)[1].decode("utf-8")
