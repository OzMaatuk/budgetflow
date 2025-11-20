# BudgetFlow User Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Setup](#setup)
3. [Using BudgetFlow](#using-budgetflow)
4. [Understanding Reports](#understanding-reports)
5. [Troubleshooting](#troubleshooting)
6. [FAQ](#faq)

## Getting Started

### What is BudgetFlow?

BudgetFlow automatically processes your bank statements and updates your budget spreadsheet. Simply upload PDF statements to Google Drive, and BudgetFlow handles the rest.

### What You Need

- Windows 10 or 11 computer
- Google account with Drive access
- Gemini API key (get from Google AI Studio)
- Google Cloud service account (for API access)

## Setup

### Step 1: Get Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Click "Create API Key"
3. Copy the key (you'll need it during setup)

### Step 2: Create Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Drive API and Google Sheets API
4. Create service account:
   - Go to IAM & Admin → Service Accounts
   - Click "Create Service Account"
   - Download JSON key file

### Step 3: Set Up Google Drive

1. Create a folder in Google Drive (this is your Root Folder)
2. Share the folder with your service account email (found in JSON file)
3. Give "Editor" permissions
4. Copy the folder ID from the URL:
   ```
   https://drive.google.com/drive/folders/FOLDER_ID_HERE
   ```

### Step 4: Install BudgetFlow

1. Download `BudgetFlow.exe`
2. Run the executable
3. Complete the setup wizard:
   - Enter Gemini API key
   - Select service account JSON file
   - Enter Root Folder ID
   - Set polling interval (default: 5 minutes)
4. Click "Validate & Save"

### Step 5: Install as Service

1. Open PowerShell as Administrator
2. Navigate to BudgetFlow directory
3. Run:
   ```powershell
   .\install_service.ps1
   ```
4. Service will start automatically on system boot

## Using BudgetFlow

### Adding a New Customer

1. In your Root Folder, create a new folder with the customer name
2. BudgetFlow will automatically:
   - Create Archive, Error, and Duplicates subfolders
   - Create a budget report in the Outputs folder

### Uploading Statements

1. Save your bank statement as PDF
2. Upload to the customer's folder in Google Drive
3. BudgetFlow will process it within the polling interval
4. Processed file moves to Archive folder

### Folder Structure

```
Root Folder/
├── JohnDoe/              ← Upload PDFs here
│   ├── Archive/          ← Successfully processed
│   ├── Error/            ← Failed processing
│   └── Duplicates/       ← Already processed
├── JaneSmith/
│   ├── Archive/
│   ├── Error/
│   └── Duplicates/
└── Outputs/
    ├── JohnDoe_Budget.xlsx    ← Budget reports
    └── JaneSmith_Budget.xlsx
```

## Understanding Reports

### Budget Tab

The Budget tab shows your monthly totals by category:

| Category ID | Category Name | חודש 1 | חודש 2 | ... |
|-------------|---------------|--------|--------|-----|
| INC001      | אמא           | 5000   | 5000   | ... |
| VAR001      | סופר          | -2100  | -2350  | ... |

- **Category ID**: Internal identifier (don't modify!)
- **Category Name**: Hebrew category name
- **Month columns**: Monthly totals (additive)

### Raw Data Tab

The Raw Data tab logs every transaction:

| Date | Description | Amount | Category | Processed At |
|------|-------------|--------|----------|--------------|
| 01/05/2025 | שופרסל | -150.50 | סופר | 2025-05-01 14:30:00 |

### Important Notes

- **Don't modify Category ID column** - this breaks the system
- **Don't rename tabs** - Budget and Raw Data must exist
- **Values are additive** - uploading the same statement twice doubles the amounts
- **Duplicates are detected** - same file won't process twice

## Troubleshooting

### Service Not Running

**Check Status:**
```powershell
Get-ScheduledTask -TaskName "BudgetFlow"
```

**Start Service:**
```powershell
Start-ScheduledTask -TaskName "BudgetFlow"
```

**View Logs:**
```
%LOCALAPPDATA%\BudgetFlow\logs\service.log
```

### PDF Not Processing

**Possible Causes:**

1. **Unsupported Format**: BudgetFlow works with both text-based and scanned PDFs
   - Solution: Ensure file is a valid PDF format

2. **File in Subfolder**: PDFs must be in customer folder root
   - Solution: Move file to customer folder (not Archive/Error)

3. **Already Processed**: File hash matches existing entry
   - Solution: Check Duplicates folder

4. **Processing Error**: Check Error folder and logs
   - Solution: Review logs for specific error

### Wrong Categories

**Fix Vendor Mappings:**

1. Open: `%LOCALAPPDATA%\BudgetFlow\vendors\{customer}.json`
2. Edit mappings:
   ```json
   {
     "שופרסל": "סופר (מזון וטואלטיקה)",
     "דלק": "רכב (דלק, חניה)"
   }
   ```
3. Save file
4. Next statement will use updated mappings

### Sheet Structure Invalid

**Error Message:** "Invalid sheet structure"

**Causes:**
- Category ID column modified
- Budget or Raw Data tab renamed
- Month columns deleted

**Solution:**
- Don't modify sheet structure
- Create new customer folder for fresh sheet

## FAQ

### How often does BudgetFlow check for new files?

Every 5 minutes by default (configurable during setup).

### Can I process multiple customers?

Yes! Create a folder for each customer in the Root Folder.

### What happens if I upload the same file twice?

BudgetFlow detects duplicates and moves them to the Duplicates folder without processing.

### Can I modify the budget sheet?

Yes, but:
- Don't modify Column A (Category ID)
- Don't rename Budget or Raw Data tabs
- Don't delete month columns
- You can add rows, formatting, formulas in other columns

### How do I add a new category?

Categories are defined in `categories.json`. To add:
1. Stop the service
2. Edit `resources/categories.json`
3. Rebuild the executable
4. Restart the service

### What if my bank statement is in a different format?

BudgetFlow uses AI to extract transactions, so it adapts to different formats. If it fails:
- Check logs for specific errors
- Ensure PDF is text-based (not scanned)
- Contact support with sample (redacted) statement

### How do I backup my data?

1. **Budget Reports**: Already in Google Drive (Outputs folder)
2. **Configuration**: `%LOCALAPPDATA%\BudgetFlow\config.json`
3. **Vendor Cache**: `%LOCALAPPDATA%\BudgetFlow\vendors\`
4. **Logs**: `%LOCALAPPDATA%\BudgetFlow\logs\`

### Can I run BudgetFlow on multiple computers?

Yes, but only one instance should process each Root Folder to avoid conflicts.

### How do I uninstall?

1. Stop service:
   ```powershell
   Stop-ScheduledTask -TaskName "BudgetFlow"
   ```
2. Unregister service:
   ```powershell
   Unregister-ScheduledTask -TaskName "BudgetFlow" -Confirm:$false
   ```
3. Delete:
   - `C:\Program Files\BudgetFlow\`
   - `%LOCALAPPDATA%\BudgetFlow\`

### Where can I get help?

1. Check logs: `%LOCALAPPDATA%\BudgetFlow\logs\service.log`
2. Review this guide
3. Check GitHub issues
4. Contact support with log excerpts

## Tips & Best Practices

1. **Regular Monitoring**: Check Outputs folder weekly to verify processing
2. **Review Error Folder**: Investigate failed files promptly
3. **Backup Vendor Cache**: Save vendor mappings periodically
4. **Test with One Statement**: Before bulk upload, test with one file
5. **Keep Statements Organized**: Use consistent naming for easier tracking
6. **Monitor Logs**: Review logs monthly for any recurring issues

## Support

For additional help:
- Email: support@budgetflow.example.com
- GitHub: github.com/budgetflow/budgetflow
- Documentation: docs.budgetflow.example.com
