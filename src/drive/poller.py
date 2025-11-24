# src/drive/poller.py
"""Google Drive poller for monitoring customer folders."""
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from ssl import SSLError

from .models import Customer, PDFFile
from utils.logger import get_logger
from utils.retry import retry_with_backoff
from utils.auth import get_credentials

logger = get_logger()


class DrivePoller:
    """Monitors Google Drive for customer folders and PDF files."""
    
    def __init__(
        self,
        root_folder_id: str,
        service_account_path: Optional[str] = None,
        oauth_client_secrets: Optional[str] = None,
        oauth_token_path: Optional[str] = None
    ):
        self.root_folder_id = root_folder_id
        self.temp_dir = Path(os.getenv("LOCALAPPDATA")) / "BudgetFlow" / "tmp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        credentials = get_credentials(
            service_account_path=service_account_path,
            oauth_client_secrets=oauth_client_secrets,
            oauth_token_path=oauth_token_path
        )
        self.service = build("drive", "v3", credentials=credentials)
    
    @retry_with_backoff(max_retries=9, retryable_exceptions=(HttpError, SSLError, OSError, ConnectionError, TimeoutError))
    def discover_customers(self) -> List[Customer]:
        """Discover customer folders in root folder."""
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
    
    @retry_with_backoff(max_retries=9, retryable_exceptions=(HttpError, SSLError, OSError, ConnectionError, TimeoutError))
    def scan_customer_folder(self, customer: Customer) -> List[PDFFile]:
        """Scan customer folder for PDF files."""
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
            pdf_files.append(PDFFile(
                id=file["id"],
                name=file["name"],
                size=int(file["size"]),
                created_time=datetime.fromisoformat(file["createdTime"].replace("Z", "+00:00"))
            ))
        
        return pdf_files

    @retry_with_backoff(max_retries=9, retryable_exceptions=(HttpError, SSLError, OSError, ConnectionError, TimeoutError))
    def download_pdf(self, pdf_file: PDFFile, customer_id: str) -> Path:
        """Download PDF file to local temp storage."""
        customer_temp = self.temp_dir / customer_id
        customer_temp.mkdir(parents=True, exist_ok=True)
        
        local_path = customer_temp / pdf_file.name
        
        request = self.service.files().get_media(fileId=pdf_file.id)
        
        with open(local_path, "wb") as f:
            # 5MB chunk size to reduce SSL handshake frequency
            downloader = MediaIoBaseDownload(f, request, chunksize=5 * 1024 * 1024)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        
        logger.debug(f"Downloaded {pdf_file.name}")
        return local_path
    
    def move_to_archive(self, pdf_file: PDFFile, customer: Customer) -> None:
        self._move_to_subfolder(pdf_file, customer, "Archive", "archive_folder_id")
    
    def move_to_error(self, pdf_file: PDFFile, customer: Customer) -> None:
        self._move_to_subfolder(pdf_file, customer, "Error", "error_folder_id")
    
    def move_to_duplicates(self, pdf_file: PDFFile, customer: Customer) -> None:
        self._move_to_subfolder(pdf_file, customer, "Duplicates", "duplicates_folder_id")
    
    @retry_with_backoff(max_retries=9, retryable_exceptions=(HttpError, SSLError, OSError, ConnectionError, TimeoutError))
    def _move_to_subfolder(self, pdf_file: PDFFile, customer: Customer, folder_name: str, attr_name: str) -> None:
        folder_id = getattr(customer, attr_name)
        if not folder_id:
            folder_id = self._get_or_create_subfolder(customer.folder_id, folder_name)
            setattr(customer, attr_name, folder_id)
        
        self.service.files().update(
            fileId=pdf_file.id,
            addParents=folder_id,
            removeParents=customer.folder_id,
            fields="id, parents"
        ).execute()
    
    def ensure_customer_structure(self, customer: Customer) -> None:
        customer.archive_folder_id = self._get_or_create_subfolder(customer.folder_id, "Archive")
        customer.error_folder_id = self._get_or_create_subfolder(customer.folder_id, "Error")
        customer.duplicates_folder_id = self._get_or_create_subfolder(customer.folder_id, "Duplicates")
    
    @retry_with_backoff(max_retries=9, retryable_exceptions=(HttpError, SSLError, OSError, ConnectionError, TimeoutError))
    def _get_or_create_subfolder(self, parent_id: str, folder_name: str) -> str:
        query = (
            f"'{parent_id}' in parents "
            f"and name='{folder_name}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )
        
        results = self.service.files().list(
            q=query, fields="files(id)", pageSize=1
        ).execute()
        
        files = results.get("files", [])
        if files:
            return files[0]["id"]
        
        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id]
        }
        
        file = self.service.files().create(body=metadata, fields="id").execute()
        return file["id"]
