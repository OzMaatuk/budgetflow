# src/orchestrator/processor.py
"""Core processing logic with Thread-Local Safety."""
import concurrent.futures
from datetime import datetime
from typing import List, Dict
from decimal import Decimal
import itertools 
import ssl
from dataclasses import dataclass
from pathlib import Path

from config.manager import Config
from drive.poller import DrivePoller
from drive.models import Customer, PDFFile
from gemini.processor import GeminiProcessor, Transaction 
from utils.logger import get_logger
from utils.hash_registry import HashRegistry, FileRecord
from sheets.generator import SheetsGenerator, AggregatedData
from llm.vision_categorizer import VisionCategorizer
from llm.aggregator import Aggregator

logger = get_logger()

@dataclass
class ProcessingResult:
    customer_id: str
    files_processed: int = 0
    files_failed: int = 0
    transactions_extracted: int = 0

class ProcessingOrchestrator:
    """Orchestrates the flow: Drive -> Gemini -> Sheets -> Archive."""

    def __init__(self, config: Config):
        self.config = config
        self.gemini = GeminiProcessor(config)
        self.hash_registry = HashRegistry()
        self.discovery_drive = DrivePoller(
            root_folder_id=config.root_folder_id,
            service_account_path=config.service_account_path,
            oauth_client_secrets=config.oauth_client_secrets,
            oauth_token_path=config.oauth_token_path
        )


    def run_polling_cycle(self) -> List[ProcessingResult]:
        """Run one full polling cycle across all customers."""
        try:
            customers = self.discovery_drive.discover_customers()
        except Exception as e:
            logger.error(f"Failed to discover customers: {e}")
            return []

        results = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.max_concurrent_customers) as executor:
            future_to_customer = {
                executor.submit(self.process_customer_thread_safe, customer): customer 
                for customer in customers
            }
            
            for future in concurrent.futures.as_completed(future_to_customer):
                customer = future_to_customer[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Critical error processing customer {customer.id}: {e}")
                    results.append(ProcessingResult(customer.id, files_failed=1))

        return results

    def process_customer_thread_safe(self, customer: Customer) -> ProcessingResult:
        """Runs inside a worker thread with fresh Drive/Sheets clients."""
        logger.info(f"Starting processing for customer {customer.id}")
        result = ProcessingResult(customer.id)
        
        thread_drive = DrivePoller(
            root_folder_id=self.config.root_folder_id,
            service_account_path=self.config.service_account_path,
            oauth_client_secrets=self.config.oauth_client_secrets,
            oauth_token_path=self.config.oauth_token_path
        )

        # Resolve categories file path relative to repository root (`resources/categories.json`)
        try:
            categories_path = Path(__file__).resolve().parents[2] / "resources" / "categories.json"
        except Exception:
            categories_path = None

        thread_sheets = SheetsGenerator(
            root_folder_id=self.config.root_folder_id,
            service_account_path=self.config.service_account_path,
            oauth_client_secrets=self.config.oauth_client_secrets,
            oauth_token_path=self.config.oauth_token_path,
            categories_path=categories_path
        )
        
        all_new_transactions: List[Transaction] = []

        try:
            thread_drive.ensure_customer_structure(customer)
            customer.report_id = thread_sheets.get_or_create_report(customer)
            pdf_files = thread_drive.scan_customer_folder(customer)
            
            for pdf in pdf_files:
                new_txns, success = self._process_single_file(
                    pdf, customer, thread_drive, thread_sheets
                )
                
                if success:
                    result.files_processed += 1
                    result.transactions_extracted += len(new_txns)
                    all_new_transactions.extend(new_txns)
                else:
                    result.files_failed += 1
            
            # 4. Aggregate and Update Budget Sheet (THE ORIGINAL PLAN)
            if all_new_transactions:
                aggregated_data = self._aggregate_transactions(customer.id, all_new_transactions)
                
                # 4a. Append raw data to 'Raw Data' sheet
                thread_sheets.append_raw_data(customer.report_id, all_new_transactions, f"Batch_{datetime.now().strftime('%Y%m%d')}") 
                
                # 4b. Update monthly totals in 'Budget' sheet
                thread_sheets.update_budget(customer.report_id, aggregated_data)


        except Exception as e:
            logger.error(f"Error in customer loop {customer.id}: {e}")
            
        return result

    def _process_single_file(self, pdf: PDFFile, customer: Customer, drive: DrivePoller, sheets: SheetsGenerator) -> tuple[List[Transaction], bool]:
        """Process a single PDF file. Returns (transactions, success_status)."""
        local_path = None
        transactions: List[Transaction] = []
        
        try:
            local_path = drive.download_pdf(pdf, customer.id)
            file_hash = self.hash_registry.calculate_hash(local_path)
            
            if self.hash_registry.is_processed(customer.id, file_hash):
                logger.info(f"Skipping duplicate file {pdf.name}")
                drive.move_to_duplicates(pdf, customer)
                return [], True

            transactions = self.gemini.process_pdf(customer, pdf)
            
            # Archive File
            drive.move_to_archive(pdf, customer)
            
            # Record Success
            self.hash_registry.mark_processed(FileRecord(
                file_hash=file_hash,
                customer_id=customer.id,
                file_name=pdf.name,
                status="SUCCESS"
            ))
            
            return transactions, True

        except Exception as e:
            logger.error(f"Failed to process {pdf.name}: {e}")
            
            try:
                drive.move_to_error(pdf, customer)
            except Exception as move_err:
                logger.error(f"Failed to move to error folder: {move_err}")
            
            if local_path:
                file_hash = self.hash_registry.calculate_hash(local_path)
                self.hash_registry.mark_processed(FileRecord(
                    file_hash=file_hash,
                    customer_id=customer.id,
                    file_name=pdf.name,
                    status="FAILED"
                ))
            return [], False
            
        finally:
            if local_path and local_path.exists():
                try:
                    local_path.unlink()
                except:
                    pass

    def _aggregate_transactions(self, customer_id: str, transactions: List[Transaction]) -> AggregatedData:
        """Aggregate transactions by category for the month of the first transaction."""
        if not transactions:
            return AggregatedData(month=datetime.now().month, totals={}, customer_id=customer_id, transactions=[])

        first_date_str = transactions[0].date
        try:
            target_month = datetime.strptime(first_date_str, "%Y-%m-%d").month
        except:
            target_month = datetime.now().month
        
        category_totals: Dict[str, Decimal] = {}

        for txn in transactions:
            amount = Decimal(str(txn.amount))
            category = txn.category
            
            category_totals[category] = category_totals.get(category, Decimal(0)) + amount
            
        return AggregatedData(month=target_month, totals=category_totals, customer_id=customer_id, transactions=transactions)