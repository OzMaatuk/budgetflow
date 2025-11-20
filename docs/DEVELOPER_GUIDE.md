# BudgetFlow Developer Guide

## Architecture Overview

BudgetFlow follows a pipeline architecture with the following components:

```
Drive Poller → Vision Categorizer (PDF → Transactions) → Aggregator → Sheets Generator
```

### Component Responsibilities

1. **Drive Poller**: Monitors Google Drive, downloads PDFs
2. **Vision Categorizer**: Processes PDFs directly using Gemini Vision API, extracts and categorizes transactions
3. **Aggregator**: Groups transactions by category
4. **Sheets Generator**: Updates Google Sheets reports

## Development Setup

### Prerequisites

- Python 3.11+ (Python 3.13 recommended)
- Windows 10/11
- Git
- Visual C++ Build Tools (for some dependencies)

### Clone and Install

```bash
git clone https://github.com/budgetflow/budgetflow.git
cd budgetflow
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

**Note**: If you encounter build errors with numpy or other packages, ensure you have the latest pip version and that pre-built wheels are available for your Python version.

### Running Tests

```bash
python tests/run_tests.py
```

### Running Locally

```bash
# First time: run setup wizard
python -m config.setup_wizard

# Run service
python main.py
```

## Project Structure

```
budgetflow/
├── config/              # Configuration management
│   ├── manager.py       # Config encryption/decryption
│   └── setup_wizard.py  # GUI setup wizard
├── drive/               # Google Drive integration
│   ├── models.py        # Data models
│   └── poller.py        # Drive monitoring
├── pdf/                 # PDF processing (legacy)
│   └── __init__.py      # Package marker
├── llm/                 # LLM processing
│   ├── vision_categorizer.py  # PDF → Transactions (Vision API)
│   ├── vendor_cache.py  # Vendor mappings
│   ├── aggregator.py    # Transaction aggregation
│   └── models.py        # Data models
├── sheets/              # Google Sheets integration
│   └── generator.py     # Report generation
├── orchestrator/        # Workflow orchestration
│   └── processor.py     # Main processing logic
├── utils/               # Utilities
│   ├── logger.py        # Logging infrastructure
│   ├── exceptions.py    # Custom exceptions
│   ├── retry.py         # Retry decorator
│   └── hash_registry.py # Duplicate detection
├── resources/           # Static resources
│   └── categories.json  # Category definitions
├── service/             # Windows service files
│   ├── task_scheduler.xml
│   └── install_service.ps1
├── tests/               # Test suite
├── main.py              # Service entry point
└── requirements.txt     # Dependencies
```

## Key Classes

### ConfigManager

Manages encrypted configuration storage.

```python
from config import ConfigManager, Config

manager = ConfigManager()
config = Config(
    gemini_api_key="key",
    service_account_path="path/to/creds.json",
    root_folder_id="folder_id"
)
manager.save_config(config)
```

### DrivePoller

Monitors Google Drive for new files.

```python
from drive import DrivePoller

poller = DrivePoller(service_account_path, root_folder_id)
customers = poller.discover_customers()
pdf_files = poller.scan_customer_folder(customer)
local_path = poller.download_pdf(pdf_file, customer_id)
```

### VisionCategorizer

Extracts and categorizes transactions directly from PDFs using Gemini Vision API.

```python
from llm import VisionCategorizer

categorizer = VisionCategorizer(api_key, categories_path)
# Process PDF directly - no OCR or text extraction needed
transactions = categorizer.extract_transactions_from_pdf(pdf_path, customer_id)
```

### SheetsGenerator

Updates Google Sheets reports.

```python
from sheets import SheetsGenerator

generator = SheetsGenerator(service_account_path, root_folder_id, categories_path)
generator.update_budget(customer_id, aggregated_data)
generator.append_raw_data(customer_id, transactions)
```

### ProcessingOrchestrator

Coordinates the entire workflow.

```python
from orchestrator import ProcessingOrchestrator

orchestrator = ProcessingOrchestrator(config)
results = orchestrator.run_polling_cycle()
```

## Adding New Features

### Adding a New Category

1. Edit `resources/categories.json`:
   ```json
   {
     "variable_expenses": [
       {"id": "VAR006", "name": "חדש"}
     ]
   }
   ```

2. Rebuild executable:
   ```bash
   .\build.ps1
   ```

### Adding a New Component

1. Create module in appropriate directory
2. Define clear interface
3. Add error handling
4. Write unit tests
5. Update orchestrator to use component

### Modifying LLM Prompt

Edit `llm/vision_categorizer.py`, method `_build_vision_prompt()`:

```python
def _build_vision_prompt(self) -> str:
    return f"""Your custom prompt here
    
    Categories: {self.category_list}
    
    Return JSON format...
    """
```

## Error Handling

### Exception Hierarchy

```
BudgetFlowError
├── ConfigError
├── NetworkError
│   └── RetryableNetworkError
├── PDFError
├── LLMError
│   └── RetryableLLMError
├── SheetsError
└── ValidationError
```

### Retry Logic

Use `@retry_with_backoff` decorator for retryable operations:

```python
from utils import retry_with_backoff, RetryableNetworkError

@retry_with_backoff(max_retries=3, retryable_exceptions=(RetryableNetworkError,))
def api_call():
    # Your code here
    pass
```

## Logging

### Setting Customer Context

```python
from utils import set_customer_context

set_customer_context("customer_id")
logger.info("This log will include customer context")
set_customer_context(None)  # Clear context
```

### Log Levels

- **DEBUG**: Detailed processing steps
- **INFO**: Normal operations
- **WARNING**: Recoverable issues
- **ERROR**: Processing failures
- **CRITICAL**: Service cannot continue

## Testing

### Unit Tests

Test individual components in isolation:

```python
import unittest
from llm.vendor_cache import VendorCache

class TestVendorCache(unittest.TestCase):
    def test_lookup(self):
        cache = VendorCache()
        cache.add_mapping("customer", "vendor", "category")
        result = cache.lookup("customer", "vendor")
        self.assertEqual(result, "category")
```

### Integration Tests

Test component interactions with mocks:

```python
from unittest.mock import Mock, patch

@patch('drive.poller.build')
def test_drive_integration(mock_build):
    mock_service = Mock()
    mock_build.return_value = mock_service
    # Test code here
```

## Building and Deployment

### Building Executable

```powershell
.\build.ps1
```

This creates `dist/BudgetFlow.exe`.

**Important Notes**:
- The build script automatically handles dependency installation
- PyInstaller is configured to use absolute imports (not relative imports)
- All custom modules are explicitly listed in `hiddenimports` in `budgetflow.spec`
- The build process may take 5-10 minutes on first run

### Manual Build

```bash
# Ensure all dependencies are installed
pip install -r requirements.txt
pip install pyinstaller

# Clean build
pyinstaller budgetflow.spec --clean
```

### Common Build Issues

**Issue**: `ModuleNotFoundError` when running the executable
- **Solution**: Ensure all custom modules are listed in `hiddenimports` in `budgetflow.spec`
- **Solution**: Use absolute imports (e.g., `from config import`) instead of relative imports (e.g., `from ..config import`)

**Issue**: `pywin32` version not found
- **Solution**: Update `requirements.txt` to use `pywin32>=307` instead of a specific version

**Issue**: numpy build fails
- **Solution**: Upgrade pip: `pip install --upgrade pip`
- **Solution**: Install pre-built wheel: `pip install numpy`

### Installing Service

```powershell
cd dist
.\install_service.ps1
```

## Performance Optimization

### Concurrent Processing

Adjust `max_concurrent_customers` in config:

```python
config = Config(
    # ...
    max_concurrent_customers=5  # Process 5 customers in parallel
)
```

### Caching

Vendor cache is automatically maintained per customer at:
```
%LOCALAPPDATA%\BudgetFlow\vendors\{customer_id}.json
```

### Database Optimization

Hash registry uses SQLite with indexes:

```sql
CREATE INDEX idx_customer_hash ON processed_files(customer_id, file_hash);
```

## Security Considerations

### Credential Storage

- Configuration encrypted with Windows DPAPI
- Service account JSON stored with user-only permissions
- No credentials in logs

### API Access

- Service account has minimal permissions
- Drive folders shared only with service account
- No public access

### Data Protection

- Temporary files deleted after processing
- Customer data isolated
- No sensitive data in logs

## Troubleshooting Development Issues

### Import Errors

Ensure you're in the virtual environment:
```bash
venv\Scripts\activate
```

### API Errors

Check credentials and permissions:
```python
from google.oauth2 import service_account
credentials = service_account.Credentials.from_service_account_file(
    "path/to/creds.json"
)
# Test credentials
```

### Build Errors

Clean build artifacts:
```bash
rmdir /s /q build dist
pyinstaller budgetflow.spec --clean
```

### Module Import Errors in Executable

If the executable fails with `ModuleNotFoundError`:

1. **Check import style**: All imports in the codebase must use absolute imports:
   ```python
   # ✓ Correct
   from config import ConfigManager
   from utils import get_logger
   
   # ✗ Wrong (doesn't work with PyInstaller)
   from ..config import ConfigManager
   from ..utils import get_logger
   ```

2. **Update hiddenimports**: Add missing modules to `budgetflow.spec`:
   ```python
   hiddenimports=[
       'config',
       'config.manager',
       'orchestrator',
       'orchestrator.processor',
       # ... add all custom modules
   ]
   ```

3. **Rebuild cleanly**:
   ```powershell
   Remove-Item -Recurse -Force build, dist
   .\build.ps1
   ```

## Contributing

### Code Style

- Follow PEP 8
- Use type hints
- Document all public methods
- Write docstrings

### Pull Request Process

1. Fork repository
2. Create feature branch
3. Write tests
4. Update documentation
5. Submit PR with description

### Commit Messages

Use conventional commits:
```
feat: add new category support
fix: resolve Hebrew text reversal issue
docs: update developer guide
test: add vendor cache tests
```

## API Reference

### ConfigManager

```python
class ConfigManager:
    def load_config() -> Optional[Config]
    def save_config(config: Config) -> None
    def validate_config(config: Config) -> tuple[bool, str]
    def encrypt_sensitive_data(data: str) -> bytes
    def decrypt_sensitive_data(encrypted_data: bytes) -> str
```

### DrivePoller

```python
class DrivePoller:
    def discover_customers() -> List[Customer]
    def scan_customer_folder(customer: Customer) -> List[PDFFile]
    def download_pdf(pdf_file: PDFFile, customer_id: str) -> Path
    def move_to_archive(pdf_file: PDFFile, customer: Customer) -> None
    def move_to_error(pdf_file: PDFFile, customer: Customer) -> None
    def ensure_customer_structure(customer: Customer) -> None
```

### VisionCategorizer

```python
class VisionCategorizer:
    def __init__(api_key: str, categories_path: Path)
    def extract_transactions_from_pdf(pdf_path: Path, customer_id: str) -> List[Transaction]
    def extract_transactions_from_text(text: str, customer_id: str) -> List[Transaction]
    def infer_month(transactions: List[Transaction]) -> int
```

### SheetsGenerator

```python
class SheetsGenerator:
    def __init__(service_account_path: str, root_folder_id: str, categories_path: Path)
    def get_or_create_report(customer_id: str) -> str
    def update_budget(customer_id: str, aggregated: AggregatedData) -> None
    def append_raw_data(customer_id: str, transactions: List[Transaction]) -> None
    def validate_structure(spreadsheet_id: str) -> bool
```

## Resources

- [Google Drive API](https://developers.google.com/drive/api/v3/about-sdk)
- [Google Sheets API](https://developers.google.com/sheets/api)
- [Gemini API](https://ai.google.dev/docs)
- [Google GenAI SDK](https://googleapis.github.io/python-genai/)
- [PyInstaller](https://pyinstaller.org/en/stable/)

## Support

For development questions:
- GitHub Issues: github.com/budgetflow/budgetflow/issues
- Developer Chat: discord.gg/budgetflow
- Email: dev@budgetflow.example.com
