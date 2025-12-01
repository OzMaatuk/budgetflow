"""Authentication utilities for Google APIs."""
import os
import pickle
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from utils.logger import get_logger

logger = get_logger()

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets"
]


def get_default_token_path() -> str:
    """Get default OAuth token path."""
    config_dir = Path(os.getenv("LOCALAPPDATA")) / "BudgetFlow"
    config_dir.mkdir(parents=True, exist_ok=True)
    return str(config_dir / "token.pickle")


def get_credentials(
    service_account_path: Optional[str] = None,
    oauth_client_secrets: Optional[str] = None,
    oauth_token_path: Optional[str] = None
):
    """
    Get Google API credentials using either service account or OAuth 2.0.
    
    Args:
        service_account_path: Path to service account JSON (optional)
        oauth_client_secrets: Path to OAuth client secrets JSON (optional)
        oauth_token_path: Path to save/load OAuth token pickle (optional)
        
    Returns:
        Credentials object for Google APIs
        
    Raises:
        ValueError: If neither authentication method is configured
    """
    # Try service account first
    if service_account_path and os.path.exists(service_account_path):
        logger.info("Using service account authentication")
        return service_account.Credentials.from_service_account_file(
            service_account_path,
            scopes=SCOPES
        )
    
    # Try OAuth 2.0
    if oauth_client_secrets:
        logger.info("Using OAuth 2.0 authentication")
        return _get_oauth_credentials(oauth_client_secrets, oauth_token_path)
    
    raise ValueError(
        "No authentication method configured. "
        "Provide either service_account_path or oauth_client_secrets."
    )


def _get_oauth_credentials(
    client_secrets_path: str,
    token_path: Optional[str] = None
) -> Credentials:
    """
    Get OAuth 2.0 credentials with automatic refresh.
    
    Args:
        client_secrets_path: Path to client_secrets.json
        token_path: Path to save/load token pickle
        
    Returns:
        OAuth credentials
    """
    if token_path is None:
        token_path = get_default_token_path()
    
    creds = _load_existing_credentials(token_path)
    
    if not creds or not creds.valid:
        creds = _refresh_or_authorize(creds, client_secrets_path)
        _save_credentials(creds, token_path)
    
    return creds


def _load_existing_credentials(token_path: str) -> Optional[Credentials]:
    """Load existing OAuth credentials from file."""
    if os.path.exists(token_path):
        try:
            logger.debug("Loading saved OAuth credentials")
            with open(token_path, "rb") as token:
                return pickle.load(token)
        except Exception as e:
            logger.warning(f"Failed to load credentials from {token_path}: {e}")
            logger.info("Will delete corrupted token file and re-authorize")
            try:
                os.remove(token_path)
            except Exception:
                pass
    return None


def _refresh_or_authorize(creds: Optional[Credentials], client_secrets_path: str) -> Credentials:
    """Refresh expired credentials or start new authorization flow."""
    if creds and creds.expired and creds.refresh_token:
        try:
            logger.info("Refreshing expired OAuth credentials")
            creds.refresh(Request())
            logger.info("OAuth credentials refreshed successfully")
            return creds
        except Exception as e:
            logger.warning(f"Failed to refresh credentials: {e}")
            logger.info("Token refresh failed, will re-authorize")
            creds = None
    
    if not os.path.exists(client_secrets_path):
        raise FileNotFoundError(
            f"OAuth client secrets not found: {client_secrets_path}\n"
            "Please create OAuth credentials in Google Cloud Console."
        )
    
    logger.info("Starting OAuth authorization flow (token expired or revoked)")
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_path, SCOPES)
    creds = flow.run_local_server(port=0)
    logger.info("OAuth authorization successful")
    return creds


def _save_credentials(creds: Credentials, token_path: str) -> None:
    """Save OAuth credentials to file."""
    with open(token_path, "wb") as token:
        pickle.dump(creds, token)
        logger.debug(f"Saved OAuth credentials to {token_path}")
