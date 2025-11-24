# src/gemini/processor.py
"""Gemini AI processor for extracting financial data using modern google-genai SDK."""
import json
import time
import re # Import regex for advanced cleaning
from dataclasses import dataclass
from pathlib import Path
from typing import List

from google import genai
from google.genai import types

from config.manager import Config
from utils.logger import get_logger
from utils.retry import retry_with_backoff
from drive.models import Customer, PDFFile
from llm.models import Transaction
from utils.exceptions import PDFError, LLMError, SheetsError, NetworkError
from utils.hash_registry import HashRegistry, FileRecord
from drive.poller import DrivePoller
from sheets.generator import SheetsGenerator, AggregatedData
from llm.vision_categorizer import VisionCategorizer
from llm.aggregator import Aggregator

logger = get_logger()

class GeminiProcessor:
    """Handles interaction with Gemini API using the new Client SDK."""

    def __init__(self, config: Config):
        self.config = config
        self.client = genai.Client(api_key=config.gemini_api_key)
        self.model_name = "gemini-2.5-flash-lite"
        self.hash_registry = HashRegistry()
        self.drive_poller = DrivePoller(
            root_folder_id=config.root_folder_id,
            service_account_path=config.service_account_path,
            oauth_client_secrets=config.oauth_client_secrets,
            oauth_token_path=config.oauth_token_path
        )
        categories_path = Path(__file__).parent.parent.parent / "resources" / "categories.json"
        self.vision_categorizer = VisionCategorizer(config.gemini_api_key, categories_path)
        self.sheets_generator = SheetsGenerator(
            root_folder_id=self.config.root_folder_id,
            service_account_path=self.config.service_account_path,
            oauth_client_secrets=self.config.oauth_client_secrets,
            oauth_token_path=self.config.oauth_token_path,
            categories_path=categories_path
        )
        self.aggregator = Aggregator()

    @retry_with_backoff(max_retries=3)
    def process_pdf(self, customer: Customer, pdf_file: PDFFile) -> List:
        """
        Process a single PDF file.
        ...
        """
        logger.info(f"Processing file: {pdf_file.name}")
        
        local_path = None
        
        try:
            # --- Existing Logic ---
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

            # --- Sheets Integration (Crucial Update) ---
            # 1. Get or Create the Report Spreadsheet ID
            categories_path = Path(__file__).parent.parent / "resources" / "categories.json"
            spreadsheet_id = self.sheets_generator.get_or_create_report(customer)
            
            # 2. Update Sheets using the ID and original logic
            # SheetsGenerator.update_budget(self, spreadsheet_id: str, aggregated: AggregatedData)
            # NOTE: We use the actual spreadsheet_id here.
            self.sheets_generator.update_budget(spreadsheet_id, aggregated) 
            
            # SheetsGenerator.append_raw_data(self, spreadsheet_id: str, transactions: List[Transaction], source_file: str)
            self.sheets_generator.append_raw_data(spreadsheet_id, transactions, pdf_file.name)
            
            # --- Post-Processing Logic ---
            self.drive_poller.move_to_archive(pdf_file, customer)
            
            # Mark as processed
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
            
        except (PDFError, LLMError, SheetsError, NetworkError) as e:
            # ... (Error handling remains the same)
            # ... (Mark as error in registry, move to error folder)
            raise

    def _parse_response(self, text: str) -> List[Transaction]:
        """Parse structured JSON response with additional cleanup for common LLM errors."""
        try:
            clean_text = text.strip()
            
            # 1. Strip markdown code blocks (```json ... ```)
            if clean_text.startswith("```"):
                clean_text = re.sub(r'^(```json|```)', '', clean_text).strip()
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3].strip()
            
            # 2. FIX: Remove trailing commas before a closing bracket or brace
            # This is the most common cause of "Expecting ',' delimiter"
            clean_text = re.sub(r',\s*([\]}])', r'\1', clean_text)
            
            # 3. Load the JSON. Set strict=False to potentially handle some non-standard characters
            # and invalid JSON escape sequences more gracefully (though not a guarantee).
            data = json.loads(clean_text, strict=False) 
            
            transactions = []
            items = data if isinstance(data, list) else data.get("transactions", [])
            
            for item in items:
                transactions.append(Transaction(
                    date=item.get("date", ""),
                    description=item.get("description", "Unknown"),
                    amount=float(item.get("amount", 0.0)),
                    category=item.get("category", "Uncategorized"),
                    currency=item.get("currency", "USD")
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"Raw response (first 100 chars): {text[:100]}...")
            # Re-raise the parsing error for logging and retry logic
            raise Exception(f"Failed to parse Gemini JSON: {e}")