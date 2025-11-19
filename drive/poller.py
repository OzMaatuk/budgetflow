"""Google Drive poller for monitoring customer folders."""
import os
import io
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

from .models import Customer, PDFFile
from budgetflow.utils import get_logger, RetryableNetworkError, retry_with_backoff

logger = get_logger()


class DrivePoller:
    """Monitors Google Drive for customer folders and PDF files."""
    
    def __init__(self, service_account_path: str, root_folder_id: str):
        """
        Initialize Drive poller.
        
        Args:
            service_account_path: Path to service account JSON file
            root_folder_id: ID of root folder containing customer folders
        """
        self.root_folder_id = root_folder_id
        self.temp_dir = Path(os.getenv("LOCALAPPDATA")) / "BudgetFlow" / "tmp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Drive API
        credentials = service_account.Credentials.from_service_account_file(
            service_account_path,
            scopes=["https://www.googleapis.com/auth/drive"]
        )
        self.service = build("drive", "v3", credentials=credentials)
        logger.info("Drive API initialized")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def discover_customers(self) -> List[Customer]:
        """
        Discover customer folders in root folder.
        
        Returns:
            List of Customer objects
        """
        try:
            # List all folders in root, excluding Outputs
            query = (
                f"'{self.root_folder_id}' in parents "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false"
            )
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name)",
                pageSize=100
            ).execute()
            
            folders = results.get("files", [])
            customers = []
            
            for folder in folders:
                if folder["name"] == "Outputs":
                    continue
                
                customer = Customer(
                    id=folder["name"],
                    folder_id=folder["id"]
                )
                customers.append(customer)
            
            logger.info(f"Discovered {len(customers)} customers")
            return customers
            
        except HttpError as e:
            logger.error(f"Failed to discover customers: {e}")
            raise RetryableNetworkError(f"Drive API error: {e}")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def scan_customer_folder(self, customer: Customer) -> List[PDFFile]:
        """
        Scan customer folder for PDF files.
        
        Args:
            customer: Customer object
            
        Returns:
            List of PDFFile objects
        """
        try:
            # List PDF files in customer folder (not in subfolders)
            query = (
                f"'{customer.folder_id}' in parents "
                f"and mimeType='application/pdf' "
                f"and trashed=false"
            )
            
            results = self.service.files().list(
                q=query,
                fields="files(id, name, size, createdTime)",
                pageSize=100
            ).execute()
            
            files = results.get("files", [])
            pdf_files = []
            
            for file in files:
                pdf_file = PDFFile(
                    id=file["id"],
                    name=file["name"],
                    size=int(file["size"]),
                    created_time=datetime.fromisoformat(file["createdTime"].replace("Z", "+00:00"))
                )
                pdf_files.append(pdf_file)
            
            logger.debug(f"Found {len(pdf_files)} PDF files for customer {customer.id}")
            return pdf_files
            
        except HttpError as e:
            logger.error(f"Failed to scan customer folder {customer.id}: {e}")
            raise RetryableNetworkError(f"Drive API error: {e}")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def download_pdf(self, pdf_file: PDFFile, customer_id: str) -> Path:
        """
        Download PDF file to local temp storage.
        
        Args:
            pdf_file: PDFFile object
            customer_id: Customer identifier
            
        Returns:
            Path to downloaded file
        """
        try:
            # Create customer-specific temp directory
            customer_temp = self.temp_dir / customer_id
            customer_temp.mkdir(parents=True, exist_ok=True)
            
            local_path = customer_temp / pdf_file.name
            
            # Download file
            request = self.service.files().get_media(fileId=pdf_file.id)
            
            with open(local_path, "wb") as f:
                downloader = MediaIoBaseDownload(f, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
            
            logger.info(f"Downloaded {pdf_file.name} for customer {customer_id}")
            return local_path
            
        except HttpError as e:
            logger.error(f"Failed to download {pdf_file.name}: {e}")
            raise RetryableNetworkError(f"Drive API error: {e}")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def move_to_archive(self, pdf_file: PDFFile, customer: Customer) -> None:
        """
        Move PDF file to customer's Archive folder.
        
        Args:
            pdf_file: PDFFile object
            customer: Customer object
        """
        try:
            if not customer.archive_folder_id:
                customer.archive_folder_id = self._get_or_create_subfolder(
                    customer.folder_id,
                    "Archive"
                )
            
            # Move file
            self.service.files().update(
                fileId=pdf_file.id,
                addParents=customer.archive_folder_id,
                removeParents=customer.folder_id,
                fields="id, parents"
            ).execute()
            
            logger.info(f"Moved {pdf_file.name} to Archive for customer {customer.id}")
            
        except HttpError as e:
            logger.error(f"Failed to move {pdf_file.name} to Archive: {e}")
            raise RetryableNetworkError(f"Drive API error: {e}")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def move_to_error(self, pdf_file: PDFFile, customer: Customer) -> None:
        """
        Move PDF file to customer's Error folder.
        
        Args:
            pdf_file: PDFFile object
            customer: Customer object
        """
        try:
            if not customer.error_folder_id:
                customer.error_folder_id = self._get_or_create_subfolder(
                    customer.folder_id,
                    "Error"
                )
            
            # Move file
            self.service.files().update(
                fileId=pdf_file.id,
                addParents=customer.error_folder_id,
                removeParents=customer.folder_id,
                fields="id, parents"
            ).execute()
            
            logger.warning(f"Moved {pdf_file.name} to Error for customer {customer.id}")
            
        except HttpError as e:
            logger.error(f"Failed to move {pdf_file.name} to Error: {e}")
            raise RetryableNetworkError(f"Drive API error: {e}")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def move_to_duplicates(self, pdf_file: PDFFile, customer: Customer) -> None:
        """
        Move PDF file to customer's Duplicates folder.
        
        Args:
            pdf_file: PDFFile object
            customer: Customer object
        """
        try:
            if not customer.duplicates_folder_id:
                customer.duplicates_folder_id = self._get_or_create_subfolder(
                    customer.folder_id,
                    "Duplicates"
                )
            
            # Move file
            self.service.files().update(
                fileId=pdf_file.id,
                addParents=customer.duplicates_folder_id,
                removeParents=customer.folder_id,
                fields="id, parents"
            ).execute()
            
            logger.info(f"Moved duplicate {pdf_file.name} for customer {customer.id}")
            
        except HttpError as e:
            logger.error(f"Failed to move {pdf_file.name} to Duplicates: {e}")
            raise RetryableNetworkError(f"Drive API error: {e}")
    
    def ensure_customer_structure(self, customer: Customer) -> None:
        """
        Ensure customer folder has required subfolders.
        
        Args:
            customer: Customer object (will be updated with folder IDs)
        """
        customer.archive_folder_id = self._get_or_create_subfolder(
            customer.folder_id,
            "Archive"
        )
        customer.error_folder_id = self._get_or_create_subfolder(
            customer.folder_id,
            "Error"
        )
        customer.duplicates_folder_id = self._get_or_create_subfolder(
            customer.folder_id,
            "Duplicates"
        )
        logger.debug(f"Ensured folder structure for customer {customer.id}")
    
    @retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError, HttpError))
    def _get_or_create_subfolder(self, parent_id: str, folder_name: str) -> str:
        """
        Get or create a subfolder.
        
        Args:
            parent_id: Parent folder ID
            folder_name: Name of subfolder
            
        Returns:
            Folder ID
        """
        try:
            # Check if folder exists
            query = (
                f"'{parent_id}' in parents "
                f"and name='{folder_name}' "
                f"and mimeType='application/vnd.google-apps.folder' "
                f"and trashed=false"
            )
            
            results = self.service.files().list(
                q=query,
                fields="files(id)",
                pageSize=1
            ).execute()
            
            files = results.get("files", [])
            
            if files:
                return files[0]["id"]
            
            # Create folder
            metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id]
            }
            
            folder = self.service.files().create(
                body=metadata,
                fields="id"
            ).execute()
            
            logger.debug(f"Created subfolder: {folder_name}")
            return folder["id"]
            
        except HttpError as e:
            logger.error(f"Failed to get/create subfolder {folder_name}: {e}")
            raise RetryableNetworkError(f"Drive API error: {e}")
    
    def cleanup_temp_file(self, file_path: Path) -> None:
        """
        Delete temporary file.
        
        Args:
            file_path: Path to file
        """
        try:
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Cleaned up temp file: {file_path.name}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {file_path}: {e}")
