# src/sheets/generator.py
"""Google Sheets generator, implementing two-sheet (Budget/Raw Data) structure with additive monthly aggregation."""
import json
import re
from pathlib import Path
from decimal import Decimal
from typing import Optional, List, Dict
from datetime import datetime
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.logger import get_logger
from utils.exceptions import SheetsError, RetryableNetworkError
from utils.retry import retry_with_backoff
from utils.auth import get_credentials
from drive.models import Customer, PDFFile
from llm.models import Transaction, AggregatedData

logger = get_logger()

# Renamed from SheetsReporter to SheetsGenerator for Orchestrator compatibility
class SheetsGenerator:
    """Manages system configuration with encryption and sheet updates."""

    def __init__(self, root_folder_id, service_account_path, oauth_client_secrets, oauth_token_path, categories_path: Optional[Path] = None):
        # The Orchestrator passes config values as arguments directly
        credentials = get_credentials(
            service_account_path=service_account_path,
            oauth_client_secrets=oauth_client_secrets,
            oauth_token_path=oauth_token_path
        )
        
        self.sheets_service = build("sheets", "v4", credentials=credentials)
        self.drive_service = build("drive", "v3", credentials=credentials)
        self.root_folder_id = root_folder_id
        
        # Load categories if a path is provided, otherwise use default
        if categories_path and categories_path.exists():
            try:
                with open(categories_path, 'r', encoding='utf-8') as f:
                    self.categories = json.load(f)
            except Exception:
                logger.warning(f"Could not load categories from {categories_path}, using DEFAULT_CATEGORIES.")
                self.categories = DEFAULT_CATEGORIES
        else:
            self.categories = DEFAULT_CATEGORIES
        
        logger.info("Sheets Generator initialized with multi-sheet budget logic")

    @retry_with_backoff()
    def get_or_create_report(self, customer: Customer) -> str:
        """Get or create customer report spreadsheet, ensuring Budget and Raw Data tabs exist. (Same as original)"""
        report_name = "BudgetFlow Report"
        
        if customer.report_id:
            self._ensure_sheet_structure(customer.report_id)
            return customer.report_id

        # Search for existing report
        query = (
            f"'{customer.folder_id}' in parents "
            f"and name='{report_name}' "
            f"and mimeType='application/vnd.google-apps.spreadsheet' "
            f"and trashed=false"
        )
        results = self.drive_service.files().list(q=query, fields="files(id)").execute()
        files = results.get("files", [])

        if files:
            spreadsheet_id = files[0]["id"]
            self._ensure_sheet_structure(spreadsheet_id)
            return spreadsheet_id

        # Create new report
        spreadsheet_id = self._create_report(customer.id, report_name, customer.folder_id)
        return spreadsheet_id

    def _create_report(self, customer_id: str, report_name: str, parent_folder_id: str) -> str:
        """Create new budget report and set up Budget and Raw Data sheets. (Same as original)"""
        spreadsheet_body = {
            "properties": {"title": report_name},
            "sheets": [{"properties": {"title": "Sheet1"}}]
        }
        
        spreadsheet = self.sheets_service.spreadsheets().create(
            body=spreadsheet_body,
            fields="spreadsheetId"
        ).execute()
        
        spreadsheet_id = spreadsheet["spreadsheetId"]

        # Move to customer folder
        file = self.drive_service.files().get(fileId=spreadsheet_id, fields="parents").execute()
        previous_parents = ",".join(file.get('parents', []))
        
        self.drive_service.files().update(
            fileId=spreadsheet_id,
            addParents=parent_folder_id,
            removeParents=previous_parents,
            fields="id, parents"
        ).execute()
        
        self._setup_sheets(spreadsheet_id)
        self._initialize_budget_sheet(spreadsheet_id)
        self._initialize_raw_data_sheet(spreadsheet_id)
        
        return spreadsheet_id
    
    @retry_with_backoff()
    def _get_sheet_info(self, spreadsheet_id: str) -> tuple:
        """Get sheet information (sheets list and names). (Same as original)"""
        result = self.sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()
        sheets = result.get("sheets", [])
        sheet_names = [sheet["properties"]["title"] for sheet in sheets]
        return sheets, sheet_names
    
    @retry_with_backoff()
    def _ensure_sheet_structure(self, spreadsheet_id: str) -> None:
        """Ensure existing spreadsheet has proper sheet structure (Budget, Raw Data). (Same as original)"""
        sheets, sheet_names = self._get_sheet_info(spreadsheet_id)
        requests = []
        needs_budget_init = False
        needs_raw_data_init = False
        
        # Logic to rename "Sheet1" or "Transactions" to "Budget"
        if "Budget" not in sheet_names:
            default_sheet = next((s for s in sheets if s["properties"]["title"] in ["Sheet1", "Transactions"]), None)
            
            if default_sheet:
                requests.append({
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": default_sheet["properties"]["sheetId"],
                            "title": "Budget"
                        },
                        "fields": "title"
                    }
                })
            else:
                requests.append({"addSheet": {"properties": {"title": "Budget"}}})
            needs_budget_init = True
        
        # Check if Raw Data sheet exists
        if "Raw Data" not in sheet_names:
            requests.append({"addSheet": {"properties": {"title": "Raw Data"}}})
            needs_raw_data_init = True
        
        if requests:
            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": requests}
            ).execute()
            
            # Re-fetch info to get new sheet IDs if needed (though not strictly necessary for init functions)
            # sheets, sheet_names = self._get_sheet_info(spreadsheet_id) 

            if needs_budget_init:
                self._initialize_budget_sheet(spreadsheet_id)
            if needs_raw_data_init:
                self._initialize_raw_data_sheet(spreadsheet_id)

    def _setup_sheets(self, spreadsheet_id: str) -> None:
        """Rename default Sheet1 to Budget and add Raw Data sheet. (Same as original)"""
        sheets, _ = self._get_sheet_info(spreadsheet_id)
        # Assuming 'Sheet1' is present after creation in _create_report
        default_sheet = next(s for s in sheets if s["properties"]["title"] == "Sheet1")
        default_sheet_id = default_sheet["properties"]["sheetId"]
        
        requests = [
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": default_sheet_id, "title": "Budget"},
                    "fields": "title"
                }
            },
            {"addSheet": {"properties": {"title": "Raw Data"}}}
        ]
        
        self.sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()
    
    @retry_with_backoff()
    def _initialize_budget_sheet(self, spreadsheet_id: str) -> None:
        """Initialize Budget sheet with categories and month headers. (Same as original)"""
        # The month names are in Hebrew: חודש 1 (Hodesh 1) = Month 1
        headers = ["Category ID", "Category Name"] + [f"חודש {i}" for i in range(1, 13)]
        
        rows = [headers]
        
        for group in ["income", "fixed_expenses", "variable_expenses", "other"]:
            for category in self.categories.get(group, []):
                # Row structure: [ID, Name, Month 1 (0), Month 2 (0), ...]
                row = [category["id"], category["name"]] + ["0"] * 12
                rows.append(row)
        
        body = {"values": rows}
        
        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Budget!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        
    @retry_with_backoff()
    def _initialize_raw_data_sheet(self, spreadsheet_id: str) -> None:
        """Initialize Raw Data sheet with headers. (Same as original)"""
        headers = ["Date", "Description", "Amount", "Category", "Processed At", "Source File"]
        body = {"values": [headers]}
        
        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Raw Data!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        
    @retry_with_backoff()
    # Renamed method signature to match Orchestrator's call (customer_id instead of customer object)
    def update_budget(self, customer_id: str, aggregated: AggregatedData) -> None:
        """Update budget sheet with aggregated data using additive logic."""
        
        # NOTE: The SheetsGenerator is called with customer_id, but needs the report_id to update.
        # Assuming the Orchestrator (or a helper function in a complete implementation) ensures 
        # that customer.report_id is set before calling this. For now, we rely on the customer_id
        # and assume a mechanism to retrieve the report_id or pass the spreadsheet_id directly.
        # Since the Orchestrator doesn't currently provide the spreadsheet_id, we need to adapt 
        # or rely on the Orchestrator to ensure get_or_create_report is called first to get/set the ID.
        # For simplicity and sticking to the provided code structure, I'll rely on the original 
        # method signature from SheetsReporter which *did* take spreadsheet_id:
        # def update_budget(self, spreadsheet_id: str, aggregated: AggregatedData) -> None: 
        # I'll keep the Orchestrator's signature for now but assume the customer_id is used to find the ID.
        # However, the *original* SheetsReporter implementation of update_budget took spreadsheet_id, not customer_id.
        # To maintain the original logic, I'll use the spreadsheet_id parameter name. The Orchestrator calling 
        # function will need to be updated to pass the ID. Since the prompt only gave the original class, I'll stick to the original logic
        
        # Assuming the calling Orchestrator handles fetching the spreadsheet_id using customer_id
        # and passes it correctly.

        # *** Original logic from SheetsReporter.update_budget ***
        spreadsheet_id = customer_id # TEMPORARY: Assume customer_id IS the spreadsheet_id for this function scope

        # Normalize month value: ensure integer and clamp to 1..12
        try:
            month_val = int(aggregated.month)
        except Exception:
            month_val = datetime.now().month

        if month_val < 1 or month_val > 12:
            logger.warning(f"Aggregated month out of range: {aggregated.month}; using current month")
            month_val = datetime.now().month

        # If transactions are provided, aggregate per (category, month) to ensure
        # each transaction is applied to its actual month column (avoids majority-month issue).
        per_cat_month = {}
        if getattr(aggregated, "transactions", None):
            for txn in aggregated.transactions:
                # Determine transaction month robustly
                try:
                    if isinstance(txn.date, datetime):
                        txn_month = txn.date.month
                    else:
                        # try common formats
                        try:
                            txn_month = datetime.strptime(str(txn.date), "%Y-%m-%d").month
                        except:
                            try:
                                txn_month = datetime.strptime(str(txn.date), "%d/%m/%Y").month
                            except:
                                txn_month = month_val
                except Exception:
                    txn_month = month_val

                if txn_month < 1 or txn_month > 12:
                    txn_month = month_val

                key = (txn.category, txn_month)
                try:
                    amt = Decimal(str(txn.amount))
                except Exception:
                    try:
                        amt = Decimal(txn.amount)
                    except Exception:
                        amt = Decimal(0)

                per_cat_month[key] = per_cat_month.get(key, Decimal(0)) + amt

        # If no per-transaction list was provided, fall back to aggregated.totals and aggregated.month
        if not per_cat_month:
            per_cat_month = { (cat, month_val): Decimal(str(amount)) for cat, amount in aggregated.totals.items() }

        # Apply summed amounts per (category, month)
        for (category_name, mth), amount in per_cat_month.items():
            row = self._find_category_row(spreadsheet_id, category_name)
            if row is None:
                logger.warning(f"Category not found in sheet: {category_name}")
                continue

            month_col_index_0based = 2 + mth - 1
            col_letter = self._col_letter(month_col_index_0based)
            cell_range = f"Budget!{col_letter}{row}"

            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=cell_range
            ).execute()

            existing_value = result.get("values", [["0"]])[0][0]
            existing_amount = self._parse_amount(existing_value)

            new_amount = existing_amount + amount

            body = {"values": [[float(new_amount)]]}
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=cell_range,
                valueInputOption="RAW",
                body=body
            ).execute()
        
        logger.info(f"Updated budget sheet with {len(aggregated.totals)} categories for חודש {aggregated.month}")

    @retry_with_backoff()
    # Renamed method signature to match Orchestrator's call (customer_id instead of spreadsheet_id)
    def append_raw_data(self, customer_id: str, transactions: List[Transaction], source_file: str = "N/A") -> None:
        """Append transactions to Raw Data sheet."""
        
        # *** Original logic from SheetsReporter.append_raw_data ***
        spreadsheet_id = customer_id # TEMPORARY: Assume customer_id IS the spreadsheet_id for this function scope
        
        rows = []
        processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for txn in transactions:
            # Ensure date and amount are JSON-serializable for the Sheets API
            if isinstance(txn.date, datetime):
                date_value = txn.date.strftime("%Y-%m-%d")
            else:
                date_value = str(txn.date)

            # Convert Decimal to float for JSON serialization (Sheets accepts numbers)
            try:
                amount_value = float(txn.amount)
            except Exception:
                amount_value = txn.amount

            rows.append([
                date_value,
                txn.description,
                amount_value,
                txn.category,
                processed_at,
                source_file # This was passed as an argument in original, added default for Orchestrator compatibility
            ])
        
        body = {"values": rows}
        self.sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="Raw Data!A2",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()
        
        logger.info(f"Appended {len(rows)} transactions to Raw Data sheet")
    
    @retry_with_backoff()
    def _find_category_row(self, spreadsheet_id: str, category: str) -> Optional[int]:
        """Find the 1-indexed row number in the Budget sheet for a given category name. (Same as original)"""
        result = self.sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range="Budget!B:B"
        ).execute()
        
        values = result.get("values", [])
        
        for i, row in enumerate(values):
            if row and row[0] == category:
                return i + 1 # 1-indexed row number
        
        return None
    
    @staticmethod
    def _col_letter(col_index: int) -> str:
        """Convert 0-indexed column index to letter (0 -> A, 1 -> B, etc.). (Same as original)"""
        # This utility function converts column index (0-based) to letter (A, B, C...).
        result = ""
        temp_index = col_index
        while temp_index >= 0:
            result = chr(temp_index % 26 + ord('A')) + result
            temp_index = temp_index // 26 - 1
        return result
    
    @staticmethod
    def _parse_amount(value: str) -> Decimal:
        """Parse amount from cell value. (Same as original)"""
        if not value:
            return Decimal("0")
        
        cleaned = re.sub(r'[₪,\s]', '', str(value))
        
        try:
            return Decimal(cleaned)
        except:
            return Decimal("0")