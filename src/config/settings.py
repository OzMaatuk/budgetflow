"""Application settings loader from YAML configuration."""
import os
import yaml
from pathlib import Path
from typing import Any, Dict
from dataclasses import dataclass


@dataclass
class AppSettings:
    """Application-wide settings loaded from config.yaml."""
    
    # App info
    app_name: str
    app_version: str
    
    # Logging
    log_level: str
    log_max_file_size_mb: int
    log_backup_count: int
    
    # Processing
    polling_interval_minutes: int
    max_concurrent_customers: int
    chunk_size_mb: int
    
    # LLM
    llm_model_name: str
    llm_max_retries: int
    llm_initial_delay_seconds: int
    llm_backoff_factor: int
    
    # Vendor cache
    vendor_cache_fuzzy_threshold: int
    
    # Retry
    retry_max_retries: int
    retry_initial_delay_seconds: int
    retry_backoff_factor: int
    
    # Paths
    config_dir: str
    config_file: str
    logs_dir: str
    log_file: str
    temp_dir: str
    vendors_dir: str
    database_file: str
    oauth_token_file: str
    
    # Google API
    google_api_scopes: list
    
    @classmethod
    def load(cls, config_path: Path = None) -> "AppSettings":
        """Load settings from YAML file."""
        if config_path is None:
            # Default to config.yaml in project root
            config_path = Path(__file__).parent.parent.parent / "config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        return cls(
            app_name=config["app"]["name"],
            app_version=config["app"]["version"],
            log_level=config["logging"]["level"],
            log_max_file_size_mb=config["logging"]["max_file_size_mb"],
            log_backup_count=config["logging"]["backup_count"],
            polling_interval_minutes=config["processing"]["polling_interval_minutes"],
            max_concurrent_customers=config["processing"]["max_concurrent_customers"],
            chunk_size_mb=config["processing"]["chunk_size_mb"],
            llm_model_name=config["llm"]["model_name"],
            llm_max_retries=config["llm"]["max_retries"],
            llm_initial_delay_seconds=config["llm"]["initial_delay_seconds"],
            llm_backoff_factor=config["llm"]["backoff_factor"],
            vendor_cache_fuzzy_threshold=config["vendor_cache"]["fuzzy_match_threshold"],
            retry_max_retries=config["retry"]["max_retries"],
            retry_initial_delay_seconds=config["retry"]["initial_delay_seconds"],
            retry_backoff_factor=config["retry"]["backoff_factor"],
            config_dir=config["paths"]["config_dir"],
            config_file=config["paths"]["config_file"],
            logs_dir=config["paths"]["logs_dir"],
            log_file=config["paths"]["log_file"],
            temp_dir=config["paths"]["temp_dir"],
            vendors_dir=config["paths"]["vendors_dir"],
            database_file=config["paths"]["database_file"],
            oauth_token_file=config["paths"]["oauth_token_file"],
            google_api_scopes=config["google_api"]["scopes"]
        )


# Global settings instance
_settings: AppSettings = None


def get_settings() -> AppSettings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = AppSettings.load()
    return _settings
