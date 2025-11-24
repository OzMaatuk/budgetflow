"""Gemini AI processor for extracting financial data."""
from pathlib import Path
from typing import List

from config.manager import Config
from utils.logger import get_logger
from utils.retry import retry_with_backoff
from drive.models import Customer, PDFFile
from llm.models import Transaction
from utils.exceptions import PDFError
from utils.hash_registry import HashRegistry, FileRecord
from drive.poller import DrivePoller
from sheets.generator import SheetsGenerator
from llm.vision_categorizer import VisionCategorizer
from llm.aggregator import Aggregator

logger = get_logger()


class GeminiProcessor:
    """Handles PDF processing using Gemini Vision API."""

    def __init__(self, config: Config):
        self.config = config
        self.hash_registry = HashRegistry()
        self.drive_poller = self._create_drive_poller(config)
        self.vision_categorizer = self._create_vision_categorizer(config)
        self.sheets_generator = self._create_sheets_generator(config)
        self.aggregator = Aggregator()
    
    def _create_drive_poller(self, config: Config) -> DrivePoller:
        """Create Drive poller instance."""
        return DrivePoller(
            root_folder_id=config.root_folder_id,
            service_account_path=config.service_account_path,
            oauth_client_secrets=config.oauth_client_secrets,
            oauth_token_path=config.oauth_token_path
        )
    
    def _create_vision_categorizer(self, config: Config) -> VisionCategorizer:
        """Create vision categorizer instance."""
        categories_path = Path(__file__).parent.parent.parent / "resources" / "categories.json"
        return VisionCategorizer(config.gemini_api_key, categories_path)
    
    def _create_sheets_generator(self, config: Config) -> SheetsGenerator:
        """Create sheets generator instance."""
        categories_path = Path(__file__).parent.parent.parent / "resources" / "categories.json"
        return SheetsGenerator(
            root_folder_id=config.root_folder_id,
            service_account_path=config.service_account_path,
            oauth_client_secrets=config.oauth_client_secrets,
            oauth_token_path=config.oauth_token_path,
            categories_path=categories_path
        )

    @retry_with_backoff(max_retries=3)
    def process_pdf(self, customer: Customer, pdf_file: PDFFile) -> List[Transaction]:
        """Process a single PDF file and extract transactions."""
        logger.info(f"Processing file: {pdf_file.name}")
        
        local_path = None
        
        try:
            local_path = self.drive_poller.download_pdf(pdf_file, customer.id)
            file_hash = self.hash_registry.calculate_hash(local_path)
            
            if self.hash_registry.is_processed(customer.id, file_hash):
                logger.info(f"File already processed (duplicate): {pdf_file.name}")
                self.drive_poller.move_to_duplicates(pdf_file, customer)
                return []
            
            transactions = self.vision_categorizer.extract_transactions_from_pdf(
                local_path,
                customer.id
            )
            
            if not transactions:
                logger.warning(f"No transactions extracted from {pdf_file.name}")
                raise PDFError("No transactions found in PDF")
            
            aggregated = self.aggregator.aggregate(transactions, customer.id)
            spreadsheet_id = self.sheets_generator.get_or_create_report(customer)
            
            self.sheets_generator.update_budget(spreadsheet_id, aggregated)
            self.sheets_generator.append_raw_data(spreadsheet_id, transactions, pdf_file.name)
            
            self.drive_poller.move_to_archive(pdf_file, customer)
            
            self.hash_registry.mark_processed(FileRecord(
                customer.id,
                file_hash,
                pdf_file.name,
                "success"
            ))
            
            logger.info(
                f"Successfully processed {pdf_file.name}: "
                f"{len(transactions)} transactions for month {aggregated.month}"
            )
            
            return transactions
            
        except Exception as e:
            logger.error(f"Failed to process {pdf_file.name}: {e}")
            
            try:
                self.drive_poller.move_to_error(pdf_file, customer)
            except Exception as move_err:
                logger.error(f"Failed to move to error folder: {move_err}")
            
            if local_path:
                file_hash = self.hash_registry.calculate_hash(local_path)
                self.hash_registry.mark_processed(FileRecord(
                    customer.id,
                    file_hash,
                    pdf_file.name,
                    "failed"
                ))
            raise
        
        finally:
            if local_path and local_path.exists():
                try:
                    local_path.unlink()
                except Exception:
                    pass
