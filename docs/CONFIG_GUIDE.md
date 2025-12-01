# Configuration Guide

## Overview

BudgetFlow now uses a two-tier configuration system:

1. **Application Settings** (`config.yaml`) - Default settings for the application
2. **User Configuration** (`%LOCALAPPDATA%\BudgetFlow\config.json`) - User-specific encrypted settings

## Application Settings (config.yaml)

### Location
Project root directory: `config.yaml`

### Purpose
Defines default application behavior and can be customized before building the executable.

### Structure

```yaml
# Application Information
app:
  name: "BudgetFlow"
  version: "1.0.0"

# Logging Configuration
logging:
  level: "INFO"              # DEBUG, INFO, WARNING, ERROR, CRITICAL
  max_file_size_mb: 10       # Maximum log file size before rotation
  backup_count: 30           # Number of backup log files to keep

# Processing Configuration
processing:
  polling_interval_minutes: 5    # How often to check for new files
  max_concurrent_customers: 3    # Number of customers to process in parallel
  chunk_size_mb: 5              # Download chunk size for large files

# LLM Configuration
llm:
  model_name: "gemini-2.5-flash-lite"  # Gemini model to use
  max_retries: 3                        # Maximum retry attempts
  initial_delay_seconds: 2              # Initial retry delay
  backoff_factor: 2                     # Exponential backoff multiplier

# Vendor Cache Configuration
vendor_cache:
  fuzzy_match_threshold: 3    # Levenshtein distance for fuzzy matching

# Retry Configuration
retry:
  max_retries: 9              # Maximum retry attempts for API calls
  initial_delay_seconds: 2    # Initial retry delay
  backoff_factor: 2           # Exponential backoff multiplier

# File Paths (relative to %LOCALAPPDATA%\BudgetFlow)
paths:
  config_dir: "."
  config_file: "config.json"
  logs_dir: "logs"
  log_file: "logs/service.log"
  temp_dir: "tmp"
  vendors_dir: "vendors"
  database_file: "budgetflow.db"
  oauth_token_file: "token.pickle"

# Google API Scopes
google_api:
  scopes:
    - "https://www.googleapis.com/auth/drive"
    - "https://www.googleapis.com/auth/drive.file"
    - "https://www.googleapis.com/auth/spreadsheets"
```

## User Configuration (config.json)

### Location
`%LOCALAPPDATA%\BudgetFlow\config.json`

### Purpose
Stores user-specific settings (encrypted with Windows DPAPI):
- Gemini API key
- Google Drive folder ID
- Authentication method (OAuth or Service Account)
- Service account path or OAuth client secrets path

### Management
- Created by setup wizard
- Encrypted automatically
- Can be reset by running setup wizard again

## Customization Examples

### Example 1: Increase Polling Interval

**Use Case**: Reduce API calls by checking less frequently

```yaml
processing:
  polling_interval_minutes: 15  # Check every 15 minutes instead of 5
```

### Example 2: Process More Customers Concurrently

**Use Case**: Faster processing with more parallel workers

```yaml
processing:
  max_concurrent_customers: 5  # Process 5 customers at once
```

### Example 3: Enable Debug Logging

**Use Case**: Troubleshooting issues

```yaml
logging:
  level: "DEBUG"  # Show detailed debug information
```

### Example 4: Adjust Vendor Matching Sensitivity

**Use Case**: More strict vendor name matching

```yaml
vendor_cache:
  fuzzy_match_threshold: 2  # Require closer match (default is 3)
```

### Example 5: Increase Retry Attempts

**Use Case**: Handle unreliable network connections

```yaml
retry:
  max_retries: 15           # Try more times
  initial_delay_seconds: 3  # Wait longer between retries
  backoff_factor: 3         # Increase delay more aggressively
```

## Using Custom Configuration

### Method 1: Modify Before Build

1. Edit `config.yaml` in project root
2. Build executable: `.\build.ps1`
3. Settings are embedded in executable

### Method 2: Runtime Override (Future Enhancement)

Currently not supported, but could be added:
- Environment variables
- Command-line arguments
- External config file path

## Configuration Loading

### In Code

```python
from config.settings import get_settings

# Get settings instance
settings = get_settings()

# Access settings
print(settings.polling_interval_minutes)
print(settings.llm_model_name)
print(settings.log_level)
```

### Settings Validation

Settings are loaded and validated at startup:
- Missing config.yaml raises FileNotFoundError
- Invalid YAML raises parsing error
- Type mismatches caught by dataclass

## File Paths

All paths in `config.yaml` are relative to `%LOCALAPPDATA%\BudgetFlow\`:

```
%LOCALAPPDATA%\BudgetFlow\
├── config.json              # User configuration (encrypted)
├── token.pickle             # OAuth token (if using OAuth)
├── budgetflow.db           # Processing history database
├── logs\
│   └── service.log         # Application logs
├── tmp\
│   └── [customer]\         # Temporary PDF downloads
└── vendors\
    └── [customer].json     # Vendor-to-category mappings
```

## Best Practices

### DO
✅ Customize settings before building
✅ Keep config.yaml in version control
✅ Document custom settings
✅ Test changes in development first
✅ Back up config.yaml before major changes

### DON'T
❌ Store secrets in config.yaml (use config.json via setup wizard)
❌ Set polling_interval_minutes too low (API rate limits)
❌ Set max_concurrent_customers too high (resource limits)
❌ Modify config.json manually (use setup wizard)
❌ Commit config.json to version control (contains secrets)

## Troubleshooting

### Config File Not Found

**Error**: `FileNotFoundError: Configuration file not found`

**Solution**: Ensure `config.yaml` exists in project root

### Invalid YAML Syntax

**Error**: `yaml.scanner.ScannerError`

**Solution**: Validate YAML syntax using online validator

### Settings Not Applied

**Issue**: Changes to config.yaml not reflected

**Solution**: Rebuild executable after modifying config.yaml

### Permission Errors

**Error**: Cannot read/write config files

**Solution**: Check file permissions in `%LOCALAPPDATA%\BudgetFlow\`

## Migration from Previous Version

If upgrading from a version without config.yaml:

1. Create `config.yaml` in project root (use provided template)
2. Install pyyaml: `pip install pyyaml>=6.0`
3. Rebuild executable: `.\build.ps1`
4. User configuration (config.json) remains compatible

## Advanced Configuration

### Custom Config Path (Future)

Could be implemented to load config from custom location:

```python
from config.settings import AppSettings

settings = AppSettings.load(Path("custom/config.yaml"))
```

### Environment Variable Overrides (Future)

Could be implemented to override settings:

```bash
BUDGETFLOW_LOG_LEVEL=DEBUG python main.py
```

### Configuration Profiles (Future)

Could support multiple profiles:

```yaml
profiles:
  development:
    logging:
      level: "DEBUG"
  production:
    logging:
      level: "INFO"
```

## Support

For configuration issues:
1. Check this guide
2. Review `config.yaml` syntax
3. Check logs at `%LOCALAPPDATA%\BudgetFlow\logs\service.log`
4. Consult IMPROVEMENTS.md for technical details
5. Open GitHub issue with configuration details

## Related Documentation

- `README.md` - General usage
- `IMPROVEMENTS.md` - Technical implementation details
- `DEVELOPER_GUIDE.md` - Development setup
- `USER_GUIDE.md` - End-user guide
