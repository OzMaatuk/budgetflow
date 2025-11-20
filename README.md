# BudgetFlow - Automated Budget Processing System

## Overview

BudgetFlow is an automated finance-processing system that runs locally on Windows. It monitors Google Drive for PDF bank statements, extracts transactions using AI, and automatically updates customer-specific Google Sheets budget reports.

## Features

- **Flexible Authentication**: OAuth 2.0 (personal accounts) or Service Account support
- **Multi-Customer Support**: Process statements for multiple customers with isolated data
- **Automatic Processing**: Polls Google Drive and processes new PDFs automatically
- **Hebrew Support**: Native Hebrew support via Gemini Vision API
- **Vision AI Processing**: Uses Gemini Vision to process PDFs directly (text-based and scanned)
- **AI Categorization**: Intelligent transaction categorization with learning
- **Vendor Learning**: Caches vendor-to-category mappings for faster processing
- **Additive Updates**: Updates budget totals without overwriting existing data
- **Complete Audit Trail**: Logs all transactions in Raw Data tab
- **Duplicate Detection**: Prevents reprocessing of the same file
- **Error Handling**: Moves failed files to Error folder for review

## System Requirements

- Windows 10/11 (64-bit)
- Python 3.11+ (for building from source)
- 2 GB RAM minimum
- 500 MB disk space
- Internet connection for API access

## Installation

### Download Release (Recommended)

1. Download the latest ZIP from [Releases](https://github.com/yourusername/budgetflow/releases)
2. Extract to any folder
3. Run `BudgetFlow.exe` - setup wizard appears automatically
4. Enter your credentials:
   - Gemini API key ([get here](https://aistudio.google.com/app/apikey))
   - **Choose authentication method:**
     - **OAuth 2.0** (recommended): Select `client_secrets.json` - see [User Guide](docs/USER_GUIDE.md#step-2-choose-authentication-method)
     - **Service Account**: Select service account JSON file
   - Google Drive folder ID
5. Click "Validate & Save"
6. **If using OAuth**: Browser opens immediately for authorization during setup

**Optional**: Install as Windows service (run as admin):
```powershell
.\install_service.ps1
```

### Build from Source

Requires Python 3.11+

```powershell
git clone https://github.com/yourusername/budgetflow.git
cd budgetflow

# Build
.\build.ps1

# Clean build
.\build.ps1 -Clean

# Build + create release ZIP
.\build.ps1 -Clean -Release
```

Output: `dist\BudgetFlow.exe`

### Project Structure

```
budgetflow/
├── src/                    # Source code
│   ├── config/            # Configuration management
│   ├── drive/             # Google Drive integration
│   ├── llm/               # AI processing
│   ├── orchestrator/      # Main workflow orchestration
│   ├── sheets/            # Google Sheets integration
│   ├── utils/             # Utilities
│   └── main.py            # Entry point
├── resources/             # Categories and assets
├── tests/                 # Unit tests
├── docs/                  # Documentation
└── main.py                # Launcher script
```

## Google Drive Structure

```
Root Folder/
├── Customer1/
│   ├── [PDF statements uploaded here]
│   ├── Archive/
│   ├── Error/
│   └── Duplicates/
├── Customer2/
│   ├── [PDF statements uploaded here]
│   ├── Archive/
│   ├── Error/
│   └── Duplicates/
└── Outputs/
    ├── Customer1_Budget.xlsx
    └── Customer2_Budget.xlsx
```

## Configuration

Configuration is stored encrypted at:
```
%LOCALAPPDATA%\BudgetFlow\config.json
```

To reconfigure, run the setup wizard again.

## Logs

Logs are stored at:
```
%LOCALAPPDATA%\BudgetFlow\logs\service.log
```

Log rotation: 30 days, 10MB per file

## Cache Management

BudgetFlow uses content-based duplicate detection (SHA256 hash). To reprocess files:

### Clear all cache
```powershell
python main.py clear-cache
```

### Clear cache for specific customer
```powershell
python main.py clear-cache --customer "Customer Name"
```

### List cached files
```powershell
# All customers
python main.py list-cache

# Specific customer
python main.py list-cache --customer "Customer Name"
```

Cache is stored at: `%LOCALAPPDATA%\BudgetFlow\registry.db`

## Service Management

### Start Service
```powershell
Start-ScheduledTask -TaskName "BudgetFlow"
```

### Stop Service
```powershell
Stop-ScheduledTask -TaskName "BudgetFlow"
```

### View Status
```powershell
Get-ScheduledTask -TaskName "BudgetFlow"
```

### Uninstall Service
```powershell
Unregister-ScheduledTask -TaskName "BudgetFlow" -Confirm:$false
```

## Troubleshooting

**Service won't start**: Check logs at `%LOCALAPPDATA%\BudgetFlow\logs\service.log`

**PDFs not processing**: Check API key validity and quota limits

**Wrong categories**: Edit vendor cache at `%LOCALAPPDATA%\BudgetFlow\vendors\{customer}.json`

## Support

Check logs: `%LOCALAPPDATA%\BudgetFlow\logs\service.log`

Open issues on GitHub with error details

## License

Copyright (c) 2025 BudgetFlow
