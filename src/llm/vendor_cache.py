"""Vendor-to-category mapping cache."""
import json
import os
from pathlib import Path
from typing import Optional, Dict
import Levenshtein

from utils.logger import get_logger

logger = get_logger()


class VendorCache:
    """Manages vendor-to-category mappings per customer with fuzzy matching."""
    
    def __init__(self, fuzzy_threshold: int = 3):
        """
        Initialize vendor cache.
        
        Args:
            fuzzy_threshold: Maximum Levenshtein distance for fuzzy match
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.cache_dir = Path(os.getenv("LOCALAPPDATA")) / "BudgetFlow" / "vendors"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def lookup(self, customer_id: str, vendor: str) -> Optional[str]:
        """
        Look up category for vendor.
        
        Args:
            customer_id: Customer identifier
            vendor: Vendor name
            
        Returns:
            Category name or None if not found
        """
        mappings = self._load_mappings(customer_id)
        
        # Normalize vendor name
        normalized_vendor = self._normalize_vendor(vendor)
        
        # Try exact match
        if normalized_vendor in mappings:
            logger.debug(f"Exact vendor match: {vendor} -> {mappings[normalized_vendor]}")
            return mappings[normalized_vendor]
        
        # Try fuzzy match
        for cached_vendor, category in mappings.items():
            distance = Levenshtein.distance(normalized_vendor, cached_vendor)
            if distance <= self.fuzzy_threshold:
                logger.debug(
                    f"Fuzzy vendor match: {vendor} -> {cached_vendor} "
                    f"(distance: {distance}) -> {category}"
                )
                return category
        
        logger.debug(f"No vendor match found for: {vendor}")
        return None
    
    def add_mapping(self, customer_id: str, vendor: str, category: str) -> None:
        """
        Add vendor-to-category mapping.
        
        Args:
            customer_id: Customer identifier
            vendor: Vendor name
            category: Category name
        """
        mappings = self._load_mappings(customer_id)
        normalized_vendor = self._normalize_vendor(vendor)
        
        if normalized_vendor not in mappings:
            mappings[normalized_vendor] = category
            self._save_mappings(customer_id, mappings)
            logger.debug(f"Added vendor mapping: {vendor} -> {category}")
    
    def get_all_mappings(self, customer_id: str) -> Dict[str, str]:
        """
        Get all vendor mappings for customer.
        
        Args:
            customer_id: Customer identifier
            
        Returns:
            Dictionary of vendor -> category mappings
        """
        return self._load_mappings(customer_id)
    
    def _load_mappings(self, customer_id: str) -> Dict[str, str]:
        """Load mappings from file."""
        cache_file = self.cache_dir / f"{customer_id}.json"
        
        if not cache_file.exists():
            return {}
        
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load vendor cache for {customer_id}: {e}")
            return {}
    
    def _save_mappings(self, customer_id: str, mappings: Dict[str, str]) -> None:
        """Save mappings to file."""
        cache_file = self.cache_dir / f"{customer_id}.json"
        
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(mappings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save vendor cache for {customer_id}: {e}")
    
    @staticmethod
    def _normalize_vendor(vendor: str) -> str:
        """Normalize vendor name for matching."""
        return vendor.strip().lower()
