"""Core processing logic with thread-local safety.

This module was cleaned after a poor merge resolution. It ensures a single,
consistent flow for per-customer processing: drive polling, PDF processing,
deduplication, and sheet updates. Thread-local Drive/Sheets clients are
created via helper methods to avoid sharing client state across threads.
"""
import concurrent.futures
from datetime import datetime
from collections import Counter
from typing import List, Dict
from decimal import Decimal
from dataclasses import dataclass
from pathlib import Path

from drive.models import Customer, PDFFile
from config.manager import Config
from drive.poller import DrivePoller
from gemini.processor import GeminiProcessor
from llm.models import Transaction, AggregatedData
from utils.logger import get_logger
from utils.hash_registry import HashRegistry, FileRecord
from sheets.generator import SheetsGenerator

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
        # Create thread-local clients via helper methods
        thread_drive = self._create_thread_drive_client()
        thread_sheets = self._create_thread_sheets_client()

        all_new_transactions: List[Transaction] = []

        try:
            thread_drive.ensure_customer_structure(customer)

            # Ensure the customer has a spreadsheet/report; create if missing.
            try:
                customer.report_id = thread_sheets.get_or_create_report(customer)
            except Exception as e:
                logger.error(f"Failed to get or create report for customer {customer.id}: {e}")

            pdf_files = thread_drive.scan_customer_folder(customer)

            for pdf in pdf_files:
                new_txns, success = self._process_single_file(pdf, customer, thread_drive, thread_sheets)

                if success:
                    result.files_processed += 1
                    result.transactions_extracted += len(new_txns)
                    all_new_transactions.extend(new_txns)
                else:
                    result.files_failed += 1

            if all_new_transactions:
                self._update_sheets_with_transactions(thread_sheets, customer, all_new_transactions)

        except Exception as e:
            logger.error(f"Error processing customer {customer.id}: {e}")

        return result
    
    def _create_thread_drive_client(self) -> DrivePoller:
        """Create thread-local Drive client."""
        return DrivePoller(
            root_folder_id=self.config.root_folder_id,
            service_account_path=self.config.service_account_path,
            oauth_client_secrets=self.config.oauth_client_secrets,
            oauth_token_path=self.config.oauth_token_path
        )
    
    def _create_thread_sheets_client(self) -> SheetsGenerator:
        """Create thread-local Sheets client."""
        categories_path = self._get_categories_path()
        return SheetsGenerator(
            root_folder_id=self.config.root_folder_id,
            service_account_path=self.config.service_account_path,
            oauth_client_secrets=self.config.oauth_client_secrets,
            oauth_token_path=self.config.oauth_token_path,
            categories_path=categories_path
        )
    
    def _get_categories_path(self) -> Path:
        """Get path to categories.json file."""
        try:
            return Path(__file__).resolve().parents[2] / "resources" / "categories.json"
        except Exception:
            return None
    
    def _update_sheets_with_transactions(
        self, 
        sheets: SheetsGenerator, 
        customer: Customer, 
        transactions: List[Transaction]
    ) -> None:
        """Update Google Sheets with aggregated transactions."""
        aggregated_data = self._aggregate_transactions(customer.id, transactions)
        batch_name = f"Batch_{datetime.now().strftime('%Y%m%d')}"

        # Ensure spreadsheet exists for this customer; create if missing
        spreadsheet_id = getattr(customer, "report_id", None)
        if not spreadsheet_id:
            try:
                spreadsheet_id = sheets.get_or_create_report(customer)
                customer.report_id = spreadsheet_id
            except Exception as e:
                logger.error(f"Failed to create/get spreadsheet for customer {customer.id}: {e}")
                return

        sheets.append_raw_data(spreadsheet_id, transactions, batch_name)
        sheets.update_budget(spreadsheet_id, aggregated_data)

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
        # Determine the target month by the most common month among transactions.
        month_counts = Counter()
        for txn in transactions:
            txn_month = None
            # txn.date may be a datetime or a string; handle both
            try:
                if isinstance(txn.date, datetime):
                    txn_month = txn.date.month
                else:
                    # Try common date formats
                    try:
                        txn_month = datetime.strptime(str(txn.date), "%Y-%m-%d").month
                    except:
                        try:
                            txn_month = datetime.strptime(str(txn.date), "%d/%m/%Y").month
                        except:
                            txn_month = datetime.now().month
            except Exception:
                txn_month = datetime.now().month

            month_counts[txn_month] += 1

        if month_counts:
            target_month = month_counts.most_common(1)[0][0]
        else:
            target_month = datetime.now().month

        category_totals: Dict[str, Decimal] = {}
        for txn in transactions:
            amount = Decimal(str(txn.amount))
            category = txn.category
            category_totals[category] = category_totals.get(category, Decimal(0)) + amount

        return AggregatedData(month=target_month, totals=category_totals, customer_id=customer_id, transactions=transactions)