"""Processing orchestrator for end-to-end workflow."""
from pathlib import Path
from dataclasses import dataclass
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from config import Config
from drive import DrivePoller, Customer, PDFFile
from llm.vision_categorizer import VisionCategorizer
from llm.aggregator import Aggregator
from sheets.generator import SheetsGenerator
from utils.logger import (
    get_logger,
    set_customer_context,
    PDFError,
    LLMError,
    SheetsError,
    NetworkError
)
from utils.hash_registry import HashRegistry

logger = get_logger()


@dataclass
class ProcessingResult:
    """Result of processing cycle."""
    customer_id: str
    files_processed: int
    files_failed: int
    transactions_extracted: int
    duration_seconds: float


class ProcessingOrchestrator:
    """Orchestrates the entire processing pipeline."""
    
    def __init__(self, config: Config):
        """
        Initialize orchestrator.
        
        Args:
            config: System configuration
        """
        self.config = config
        
        # Initialize components
        self.drive_poller = DrivePoller(
            config.service_account_path,
            config.root_folder_id
        )
        
        categories_path = Path(__file__).parent.parent / "resources" / "categories.json"
        
        # Use Vision-based categorizer (processes PDFs directly)
        self.vision_categorizer = VisionCategorizer(
            config.gemini_api_key,
            categories_path
        )
        
        self.aggregator = Aggregator()
        
        self.sheets_generator = SheetsGenerator(
            config.service_account_path,
            config.root_folder_id,
            categories_path
        )
        
        self.hash_registry = HashRegistry()
        
        logger.info("Processing Orchestrator initialized with Vision API")
    
    def run_polling_cycle(self) -> List[ProcessingResult]:
        """
        Run one polling cycle for all customers.
        
        Returns:
            List of ProcessingResult objects
        """
        set_customer_context(None)
        logger.info("Starting polling cycle")
        
        start_time = time.time()
        
        # Discover customers
        customers = self.drive_poller.discover_customers()
        
        if not customers:
            logger.info("No customers found")
            return []
        
        # Process customers concurrently
        results = []
        with ThreadPoolExecutor(max_workers=self.config.max_concurrent_customers) as executor:
            futures = {
                executor.submit(self.process_customer, customer): customer
                for customer in customers
            }
            
            for future in as_completed(futures):
                customer = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Unexpected error processing customer {customer.id}: {e}")
        
        duration = time.time() - start_time
        logger.info(
            f"Polling cycle complete: {len(results)} customers processed in {duration:.1f}s"
        )
        
        return results
    
    def process_customer(self, customer: Customer) -> ProcessingResult:
        """
        Process all PDFs for a customer.
        
        Args:
            customer: Customer object
            
        Returns:
            ProcessingResult
        """
        set_customer_context(customer.id)
        logger.info(f"Processing customer: {customer.id}")
        
        start_time = time.time()
        files_processed = 0
        files_failed = 0
        total_transactions = 0
        
        try:
            # Ensure folder structure
            self.drive_poller.ensure_customer_structure(customer)
            
            # Scan for PDFs
            pdf_files = self.drive_poller.scan_customer_folder(customer)
            
            if not pdf_files:
                logger.debug(f"No PDF files found for customer {customer.id}")
                return ProcessingResult(
                    customer_id=customer.id,
                    files_processed=0,
                    files_failed=0,
                    transactions_extracted=0,
                    duration_seconds=time.time() - start_time
                )
            
            logger.info(f"Found {len(pdf_files)} PDF files for customer {customer.id}")
            
            # Process each PDF
            for pdf_file in pdf_files:
                try:
                    transactions = self.process_pdf(customer, pdf_file)
                    total_transactions += len(transactions)
                    files_processed += 1
                except Exception as e:
                    logger.error(f"Failed to process {pdf_file.name}: {e}")
                    files_failed += 1
            
            duration = time.time() - start_time
            logger.info(
                f"Customer {customer.id} complete: "
                f"{files_processed} processed, {files_failed} failed, "
                f"{total_transactions} transactions in {duration:.1f}s"
            )
            
            return ProcessingResult(
                customer_id=customer.id,
                files_processed=files_processed,
                files_failed=files_failed,
                transactions_extracted=total_transactions,
                duration_seconds=duration
            )
            
        except Exception as e:
            logger.error(f"Failed to process customer {customer.id}: {e}")
            return ProcessingResult(
                customer_id=customer.id,
                files_processed=files_processed,
                files_failed=files_failed,
                transactions_extracted=total_transactions,
                duration_seconds=time.time() - start_time
            )
        finally:
            set_customer_context(None)
    
    def process_pdf(self, customer: Customer, pdf_file: PDFFile) -> List:
        """
        Process a single PDF file.
        
        Args:
            customer: Customer object
            pdf_file: PDFFile object
            
        Returns:
            List of transactions
        """
        logger.info(f"Processing file: {pdf_file.name}")
        
        # Calculate hash
        local_path = None
        
        try:
            # Download file
            local_path = self.drive_poller.download_pdf(pdf_file, customer.id)
            file_hash = self.hash_registry.calculate_hash(local_path)
            
            # Check if already processed
            if self.hash_registry.is_processed(customer.id, file_hash):
                logger.info(f"File already processed (duplicate): {pdf_file.name}")
                self.drive_poller.move_to_duplicates(pdf_file, customer)
                return []
            
            # Extract and categorize transactions directly from PDF using Vision API
            transactions = self.vision_categorizer.extract_transactions_from_pdf(
                local_path,
                customer.id
            )
            
            if not transactions:
                logger.warning(f"No transactions extracted from {pdf_file.name}")
                raise PDFError("No transactions found in PDF")
            
            # Aggregate
            aggregated = self.aggregator.aggregate(transactions, customer.id)
            
            # Update sheets
            self.sheets_generator.update_budget(customer.id, aggregated)
            self.sheets_generator.append_raw_data(customer.id, transactions)
            
            # Move to archive
            self.drive_poller.move_to_archive(pdf_file, customer)
            
            # Mark as processed
            self.hash_registry.mark_processed(
                customer.id,
                file_hash,
                pdf_file.name,
                "success"
            )
            
            logger.info(
                f"Successfully processed {pdf_file.name}: "
                f"{len(transactions)} transactions for month {aggregated.month}"
            )
            
            return transactions
            
        except (PDFError, LLMError, SheetsError, NetworkError) as e:
            logger.error(f"Processing error for {pdf_file.name}: {e}")
            
            # Move to error folder
            try:
                self.drive_poller.move_to_error(pdf_file, customer)
            except Exception as move_error:
                logger.error(f"Failed to move file to error folder: {move_error}")
            
            # Mark as error in registry
            if local_path:
                try:
                    file_hash = self.hash_registry.calculate_hash(local_path)
                    self.hash_registry.mark_processed(
                        customer.id,
                        file_hash,
                        pdf_file.name,
                        "error"
                    )
                except Exception as hash_error:
                    logger.error(f"Failed to mark file as error: {hash_error}")
            
            raise
            
        finally:
            # Cleanup temp file
            if local_path:
                self.drive_poller.cleanup_temp_file(local_path)
