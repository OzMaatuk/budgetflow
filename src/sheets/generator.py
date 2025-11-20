"""Google Sheets report generator and updater."""
import json
import re
from pathlib import Path
from decimal import Decimal
from typing import Optional, List, Dict
from datetime import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from llm.models import Transaction, AggregatedData
from utils.logger import get_logger
from utils.exceptions import SheetsError, RetryableNetworkError
from utils.retry import retry_with_backoff
from utils.auth import get_credentials

logger = get_logger()


class SheetsGenerator:
    """Generates and updates customer budget reports."""
    
    def __init__(
        self,
        root_folder_id: str,
        categories_path: Path,
        service_account_path: Optional[str] = None,
        oauth_client_secrets: Optional[str] = None,
        oauth_token_path: Optional[str] = None
    ):
        """
        Initialize Sheets generator.
        
        Args:
            root_folder_id: Root folder ID for finding Outputs folder
            categories_path: Path to categories.json
            service_account_path: Path to service account JSON (optional)
            oauth_client_secrets: Path to OAuth client secrets (optional)
            oauth_token_path: Path to OAuth token pickle (optional)
        """
        credentials = get_credentials(
            service_account_path=service_account_path,
            oauth_client_secrets=oauth_client_secrets,
            oauth_token_path=oauth_token_path
        )
        
        self.sheets_service = build("sheets", "v4", credentials=credentials)
        self.drive_service = build("drive", "v3", credentials=credentials)
        self.root_folder_id = root_folder_id
        self.outputs_folder_id = self._get_outputs_folder()
        self.categories = self._load_categories(categories_path)
        
        logger.info("Sheets Generator initialized")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def get_or_create_report(self, customer_id: str) -> str:
        """
        Get or create customer report spreadsheet.
        
        Args:
            customer_id: Customer identifier
            
        Returns:
            Spreadsheet ID
        """
        # Search for existing report
        report_name = customer_id
        query = (
            f"'{self.outputs_folder_id}' in parents "
            f"and name='{report_name}' "
            f"and mimeType='application/vnd.google-apps.spreadsheet' "
            f"and trashed=false"
        )
        
        try:
            results = self.drive_service.files().list(
                q=query,
                fields="files(id)",
                pageSize=1
            ).execute()
            
            files = results.get("files", [])
            
            if files:
                spreadsheet_id = files[0]["id"]
                logger.debug(f"Found existing report for {customer_id}: {spreadsheet_id}")
                # Ensure existing sheet has proper structure
                self._ensure_sheet_structure(spreadsheet_id)
                return spreadsheet_id
            
            # Create new report
            spreadsheet_id = self._create_report(customer_id, report_name)
            logger.info(f"Created new report for {customer_id}: {spreadsheet_id}")
            return spreadsheet_id
            
        except (HttpError, ConnectionError, TimeoutError) as e:
            logger.error(f"Failed to get/create report for {customer_id}: {e}")
            raise RetryableNetworkError(f"Sheets API error: {e}")
    
    def _create_report(self, customer_id: str, report_name: str) -> str:
        """Create new budget report from template."""
        try:
            # Create the file in Drive first, directly in the Outputs folder
            file_metadata = {
                "name": report_name,
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": [self.outputs_folder_id]
            }
            
            file = self.drive_service.files().create(
                body=file_metadata,
                fields="id"
            ).execute()
            
            spreadsheet_id = file.get("id")
            
            # Rename default Sheet1 to Budget and add Raw Data sheet
            self._setup_sheets(spreadsheet_id)
            
            # Initialize Budget sheet
            self._initialize_budget_sheet(spreadsheet_id)
            
            # Initialize Raw Data sheet
            self._initialize_raw_data_sheet(spreadsheet_id)
            
            return spreadsheet_id
            
        except HttpError as e:
            logger.error(f"Failed to create report: {e}")
            raise SheetsError(f"Failed to create report: {e}")
    
    def _ensure_sheet_structure(self, spreadsheet_id: str) -> None:
        """Ensure existing spreadsheet has proper sheet structure."""
        try:
            sheets, sheet_names = self._get_sheet_info(spreadsheet_id)
            requests = []
            needs_budget_init = False
            needs_raw_data_init = False
            
            # Check if Budget sheet exists
            if "Budget" not in sheet_names:
                if sheets and sheets[0]["properties"]["title"] in ["Sheet1", "שיט1"]:
                    requests.append({
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": sheets[0]["properties"]["sheetId"],
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
            
            # Execute batch update if needed
            if requests:
                self.sheets_service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": requests}
                ).execute()
                logger.debug(f"Updated sheet structure with {len(requests)} changes")
                
                if needs_budget_init:
                    self._initialize_budget_sheet(spreadsheet_id)
                if needs_raw_data_init:
                    self._initialize_raw_data_sheet(spreadsheet_id)
            
        except HttpError as e:
            logger.error(f"Failed to ensure sheet structure: {e}")
            raise SheetsError(f"Failed to ensure sheet structure: {e}")
    
    def _setup_sheets(self, spreadsheet_id: str) -> None:
        """Setup sheet tabs (rename Sheet1 to Budget, add Raw Data)."""
        try:
            sheets, _ = self._get_sheet_info(spreadsheet_id)
            default_sheet_id = sheets[0]["properties"]["sheetId"] if sheets else 0
            
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
            
            logger.debug("Setup sheet tabs: Budget, Raw Data")
            
        except HttpError as e:
            logger.error(f"Failed to setup sheets: {e}")
            raise SheetsError(f"Failed to setup sheets: {e}")
    
    def _initialize_budget_sheet(self, spreadsheet_id: str) -> None:
        """Initialize Budget sheet with template."""
        # Build header row
        headers = ["Category ID", "Category Name"] + [f"חודש {i}" for i in range(1, 13)]
        
        # Build category rows
        rows = [headers]
        
        for group in ["income", "fixed_expenses", "variable_expenses", "other"]:
            for category in self.categories.get(group, []):
                row = [category["id"], category["name"]] + ["0"] * 12
                rows.append(row)
        
        # Write to sheet
        body = {"values": rows}
        
        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Budget!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        
        logger.debug(f"Initialized Budget sheet with {len(rows)} rows")
    
    def _initialize_raw_data_sheet(self, spreadsheet_id: str) -> None:
        """Initialize Raw Data sheet with headers."""
        headers = ["Date", "Description", "Amount", "Category", "Processed At"]
        body = {"values": [headers]}
        
        self.sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range="Raw Data!A1",
            valueInputOption="RAW",
            body=body
        ).execute()
        
        logger.debug("Initialized Raw Data sheet")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def update_budget(self, customer_id: str, aggregated: AggregatedData) -> None:
        """
        Update budget sheet with aggregated data.
        
        Args:
            customer_id: Customer identifier
            aggregated: Aggregated transaction data
        """
        try:
            spreadsheet_id = self.get_or_create_report(customer_id)
            
            # Validate structure
            if not self.validate_structure(spreadsheet_id):
                raise SheetsError(f"Invalid sheet structure for customer {customer_id}")
            
            # Find month column
            month_col = self._find_month_column(spreadsheet_id, aggregated.month)
            
            # Update each category
            for category, amount in aggregated.totals.items():
                row = self._find_category_row(spreadsheet_id, category)
                if row is None:
                    logger.warning(f"Category not found in sheet: {category}")
                    continue
                
                # Read existing value
                cell_range = f"Budget!{self._col_letter(month_col)}{row}"
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=cell_range
                ).execute()
                
                existing_value = result.get("values", [[""]])[0][0]
                existing_amount = self._parse_amount(existing_value)
                
                # Calculate new value (additive)
                new_amount = existing_amount + amount
                
                # Write back
                body = {"values": [[float(new_amount)]]}
                self.sheets_service.spreadsheets().values().update(
                    spreadsheetId=spreadsheet_id,
                    range=cell_range,
                    valueInputOption="RAW",
                    body=body
                ).execute()
                
                logger.debug(
                    f"Updated {category} for month {aggregated.month}: "
                    f"{existing_amount} + {amount} = {new_amount}"
                )
            
            logger.info(f"Updated budget for customer {customer_id}, month {aggregated.month}")
            
        except HttpError as e:
            logger.error(f"Failed to update budget: {e}")
            raise RetryableNetworkError(f"Sheets API error: {e}")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def append_raw_data(self, customer_id: str, transactions: List[Transaction]) -> None:
        """
        Append transactions to Raw Data sheet.
        
        Args:
            customer_id: Customer identifier
            transactions: List of transactions
        """
        try:
            spreadsheet_id = self.get_or_create_report(customer_id)
            
            # Build rows
            rows = []
            processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            for txn in transactions:
                row = [
                    txn.date.strftime("%d/%m/%Y"),
                    txn.description,
                    float(txn.amount),
                    txn.category,
                    processed_at
                ]
                rows.append(row)
            
            # Append to sheet
            body = {"values": rows}
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range="Raw Data!A2",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
            
            logger.info(f"Appended {len(rows)} transactions to Raw Data for {customer_id}")
            
        except HttpError as e:
            logger.error(f"Failed to append raw data: {e}")
            raise RetryableNetworkError(f"Sheets API error: {e}")
    
    def validate_structure(self, spreadsheet_id: str) -> bool:
        """
        Validate sheet structure.
        
        Args:
            spreadsheet_id: Spreadsheet ID
            
        Returns:
            True if valid, False otherwise
        """
        try:
            _, sheet_names = self._get_sheet_info(spreadsheet_id)
            
            if "Budget" not in sheet_names or "Raw Data" not in sheet_names:
                logger.error("Missing required sheets")
                return False
            
            # Check Budget sheet has Category ID column
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="Budget!A1:B2"
            ).execute()
            
            values = result.get("values", [])
            if len(values) < 2:
                logger.error("Budget sheet is empty")
                return False
            
            headers = values[0]
            if len(headers) < 2 or headers[0] != "Category ID":
                logger.error("Invalid Budget sheet structure")
                return False
            
            return True
            
        except HttpError as e:
            logger.error(f"Failed to validate structure: {e}")
            return False
    
    def _get_sheet_info(self, spreadsheet_id: str) -> tuple:
        """Get sheet information (sheets list and names)."""
        result = self.sheets_service.spreadsheets().get(
            spreadsheetId=spreadsheet_id
        ).execute()
        sheets = result.get("sheets", [])
        sheet_names = [sheet["properties"]["title"] for sheet in sheets]
        return sheets, sheet_names
    
    def _find_month_column(self, spreadsheet_id: str, month: int) -> int:
        """Find column index for month."""
        # Month columns start at column C (index 3)
        # חודש 1 is column C, חודש 2 is column D, etc.
        return 2 + month  # 0-indexed, so month 1 -> column 2 (C)
    
    def _find_category_row(self, spreadsheet_id: str, category: str) -> Optional[int]:
        """Find row index for category."""
        try:
            # Read Category Name column
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range="Budget!B:B"
            ).execute()
            
            values = result.get("values", [])
            
            for i, row in enumerate(values):
                if row and row[0] == category:
                    return i + 1  # 1-indexed
            
            return None
            
        except HttpError as e:
            logger.error(f"Failed to find category row: {e}")
            return None
    
    @staticmethod
    def _col_letter(col_index: int) -> str:
        """Convert column index to letter (0 -> A, 1 -> B, etc.)."""
        result = ""
        while col_index >= 0:
            result = chr(col_index % 26 + ord('A')) + result
            col_index = col_index // 26 - 1
        return result
    
    @staticmethod
    def _parse_amount(value: str) -> Decimal:
        """Parse amount from cell value."""
        if not value:
            return Decimal("0")
        
        # Remove currency symbols and commas
        cleaned = re.sub(r'[₪,\s]', '', str(value))
        
        try:
            return Decimal(cleaned)
        except:
            return Decimal("0")
    
    def _get_outputs_folder(self) -> str:
        """Get Outputs folder ID."""
        try:
            query = (
                f"'{self.root_folder_id}' in parents "
                f"and name='Outputs' "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false"
            )
            
            results = self.drive_service.files().list(
                q=query,
                fields="files(id)",
                pageSize=1
            ).execute()
            
            files = results.get("files", [])
            
            if not files:
                raise SheetsError("Outputs folder not found")
            
            return files[0]["id"]
            
        except HttpError as e:
            raise SheetsError(f"Failed to find Outputs folder: {e}")
    
    def _load_categories(self, categories_path: Path) -> Dict:
        """Load categories from JSON."""
        try:
            with open(categories_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise SheetsError(f"Failed to load categories: {e}")
