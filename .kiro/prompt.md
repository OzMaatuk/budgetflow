As a great product manager, help me create project specs for the following: 

The goal is mapping

I want a very simple system for mapping financial transactions.
I want to enter all kinds of current account and credit transaction details files (pdfs) into the system and have it divide all transactions by income and expenses in two separate columns, by categories, and by fixed/variable/periodic expenses.
The ultimate goal of the tool is to save me time by going through each document line by line and recording it in a spreadsheet file that I have.

example for output: files attached from google drive called input_*.pdf

example for inputs: google sheet file attached from google drive called output

lets start with simple local web application that I can run localy on windows and android devices.
app will use llm to read the pdfs, google gemini is prefered using google account and api key.
wrap project with everything needed for easy setup install and use. like its for users without great knowledge with pcs.
so install should also include step asking user to input google account and api key
for development use .env

as app already working with google account, data also should be saved in google drive, as google sheets, like the example provided.
if its possible, app will automaticly determine which person the pdf os belong and calculate the new data into the right person google sheet (each person will have its own sheet and app will be managed by admin which will upload the pdf reports). if its too complicated, users can be created manually bt the admin and upload will requier admin to select which user to calculate for and update.

you should be detailed and specific. break down into sections like features, user stories, technical requirements, etc.
make everything ready to hand off to a development team.

you should use llm for pf reading with the following example how to use llm with ollama and langchain, you should understand how to make it configurable and make google gemini flash as the default llm. keep using init_chat_model, BaseChatModel and no  other class. 

# src/utils/description_matcher.py

import logging
import re
from typing import Union
# from fuzzywuzzy import fuzz
from langchain.chat_models.base import init_chat_model, BaseChatModel
from src.constants.constants import Constants
from langchain_core.messages import BaseMessage


logger = logging.getLogger(__name__)

class DescriptionMatcher:
    """Matches job descriptions using various methods."""

    def __init__(self, method: str = Constants.DEFAULT_MATCHING_METHOD, threshold: int = Constants.DEFAULT_THRESHOLD, llm_config: dict = {}, prompt_file: str = Constants.DEFAULT_PROMPT_FILE):
        logger.info(f"Initializing DescriptionMatcher with method: {method}")
        logger.debug(f"Using threshold: {threshold}, llm_config: {llm_config}")
        self.method = method
        self.threshold = threshold

        with open(prompt_file, 'r') as file:
            self.prompt = file.read()
        
        self.llm : Union[BaseChatModel, None] = None
        if self.method == "llm":
            logger.debug("Initializing LLM model")
            if llm_config == {}:
                llm_config = {
                    "model": Constants.DEFAULT_MODEL_NAME,
                    "model_provider": Constants.DEFAULT_MODEL_PROVIDER,
                    "base_url": Constants.DEFAULT_MODEL_URL
                }
            self.llm = init_chat_model(**llm_config)
            logger.info("LLM model initialized successfully")

    def matches(self, job_description: str, user_description: str) -> bool:
        logger.debug("DescriptionMatcher.matches")
        
        if not isinstance(job_description, str) or not isinstance(user_description, str) or not job_description.strip() or not user_description.strip():
            raise ValueError("Job descriptions must be strings and cannot be empty")
        
        if self.llm is not None:
            self.prompt = self.prompt.format(job_description=job_description, user_description=user_description)
            logger.debug(f"LLM prompt: {self.prompt}")
            response = self.llm.invoke(self.prompt)
            logger.debug(f"LLM Response: {response}")
            response = str(response.content) if hasattr(response, 'content') else str(response)
            logger.debug(f"LLM Extracted Response: {response}")
            try:
                match = re.search(r'\d+', response)
                if match:
                    score = int(match.group())
                else:
                    raise ValueError("No number found in string") 
            except Exception:
                logger.error(f"Could not parse score from LLM response: {response}")
                return False
            logger.debug(f"Generated score: {score}")
            logger.debug(f"Check if score >= self.threshold: {score} >= {self.threshold}")
            return score >= self.threshold
        else:
            logger.error(f"Invalid matching method in config file: {self.method}")
            raise ValueError(f"Invalid matching method in config file: {self.method}")  


dont forget to make stuf configurable, following coding vest practice and patterns, modern stack and latest packages, great syntax, encapsulation and simplicity.
read relevant documantion for related packages (langchain for example)

think that python is the right choice here.
























Below is the **FULL, CLEAN, FINAL PRD + TECHNICAL SPEC** — rewritten to include *all discovered issues, all fixes, all architecture clarifications, all implementation details,* and everything a development team needs to begin work immediately.

It is structured, explicit, and production-grade.

---

# 🚀 **BudgetFlow – Automated Monthly Budget System**

### **Product Requirement Document (PRD) + Technical Specifications (Final Version)**

*Version 2 — Includes risk fixes, tech constraints, and full-stack design.*

---

# 1. Executive Summary

**BudgetFlow** is an automated finance-processing system that runs **locally on a Windows PC**.
Users upload PDF bank/credit card statements into a **Google Drive folder** (from PC or Android).
A local background service **polls Drive**, downloads new PDFs, extracts transactions, categorizes them using **Gemini Flash**, aggregates totals per category and month, then **updates a predefined Google Sheets budget**.

The system achieves:

* Zero manual typing
* Seamless mobile use (via Google Drive upload)
* Local-only sensitive processing
* Clear audit trail (PDF archive + Raw Data tab)

---

# 2. Scope & Goals

## 2.1 Goals

* One-click setup for normal users.
* Automatic processing of new statements.
* Accurate category mapping.
* Seamless integration with an existing Google Sheet structure.
* Reliable 24/7 background execution.

## 2.2 Out of Scope (for MVP)

* OCR for scanned PDFs (error-out instead).
* Real-time Drive push notifications (Polling only).
* Multi-currency or multi-lingual statements.
* Multi-user support.

---

# 3. High-Level Workflow

1. **User uploads PDF → Google Drive Input folder**
2. **Local Windows service polls Drive** every X minutes.
3. If new PDF exists:

   * Download to local temp
   * Extract text using PDF parser
   * Clean + normalize Hebrew text
   * Send to LLM for structured JSON extraction
   * Categorize according to strict category list
   * Infer month from transaction dates
   * Aggregate totals per category
   * Update Google Sheet cell values (+ additive)
4. **Move PDF to Drive/Archive**
5. **Log success/failure**

---

# 4. Architecture

## 4.1 System Components

| Component       | Technology                           | Purpose                         |
| --------------- | ------------------------------------ | ------------------------------- |
| Local Processor | Python 3.11+ EXE                     | Runs entire automation          |
| Drive Poller    | google-api-python-client             | Detect & download PDFs          |
| PDF Extractor   | pdfplumber (primary), pypdf fallback | Convert PDF → text              |
| LLM Extractor   | Gemini 1.5 Flash (via LangChain)     | Parse + categorize transactions |
| Sheets Writer   | gspread or Google Sheets API         | Update budget sheet             |
| Scheduler       | Windows Task Scheduler               | Runs service at startup         |
| Packaging       | PyInstaller                          | Produce EXE                     |

---

## 4.2 Data Flow Diagram (Textual)

```
Google Drive (Input Folder)
        ↓  (poll)
Local Python Service
        ↓
Download PDF (temp)
        ↓
PDF Text Extraction
        ↓
Hebrew Text Normalization
        ↓
LLM Transaction Processor
        ↓
Category Mapping + Aggregation
        ↓
Google Sheets Update
        ↓
Move PDF → Drive Archive
```

---

# 5. Detailed Functional Requirements

## 5.1 Setup Wizard (First Launch)

On first execution, the EXE must launch a setup wizard (GUI or browser-page) asking the user for:

1. **Gemini API Key**
2. **Google Service Account Credentials File (credentials.json)**
3. **Google Sheet ID**
4. **Drive Input Folder ID**
5. **Drive Archive Folder ID**
6. **Polling frequency** (default: 5 minutes)

The wizard must:

* Validate API access.
* Validate sheet exists / row & column structure.
* Validate Drive folders exist and are shared with service account.

All validated settings are saved to:

```
C:\Users\<User>\AppData\Local\BudgetFlow\config.json
```

Encrypted using Windows DPAPI.

---

## 5.2 Google Drive Watcher

### Requirements

* Poll Drive Input Folder every X minutes.
* Identify PDF files.
* Skip files already processed (via SHA256 hash registry).
* Download PDFs to:

  ```
  %LOCALAPPDATA%\BudgetFlow\tmp\
  ```
* Mark them as “processing” using Drive metadata or local DB.

### File Handling Rules

| Case                    | Action                    |
| ----------------------- | ------------------------- |
| Success                 | Move to Archive folder    |
| LLM/PDF failure         | Move to Errors folder     |
| Duplicate file detected | Move to Duplicates folder |

---

## 5.3 PDF Extraction Module

### Requirements

* Use `pdfplumber` (primary)
* Use `pypdf` fallback
* Detect invalid or scanned PDFs:

  * If extracted text length < 100 chars → "OCR unsupported"

### Hebrew Fixes

* Reverse line direction if needed.
* Normalize Unicode bidi characters.
* Strip legal footers & repeating headers.

---

## 5.4 LLM Transaction Processor

### Responsibilities

* Extract structured JSON using Gemini Flash with deterministic prompt.
* Validate JSON schema with pydantic.
* Fields:

  ```json
  {
    "date": "DD/MM/YYYY",
    "description": "string",
    "amount": -123.45,
    "category": "סופר (מזון וטואלטיקה)"
  }
  ```

### Categorization Logic

Order of resolution:

1. **Vendor Cache** (lookup.json)
2. **LLM categorization**
3. **Fallback: "Other"**

### Month Inference

* Extract month from transaction date (majority wins).
* Convert month → sheet header (e.g., MONTH 5 or חודש 5).

---

## 5.5 Category Mapping

The system uses `categories.json`:

```json
{
  "income": [...],
  "fixed_expenses": [...],
  "variable_expenses": [...],
  "other": ["Other"]
}
```

### Additional Mapping Requirements

* Must match Google Sheet row labels EXACTLY.
* Sheet must include stable category IDs in a hidden column (added in setup).

---

## 5.6 Google Sheets Update Module

### Requirements

1. Locate correct **month column** by matching header text.
2. Locate **row** using category internal ID (Column B).
3. Fetch existing numeric value:

   * Clean currency symbols ("₪", ",")
4. **Add** aggregated value (do NOT overwrite).
5. Write updated value back.
6. Append raw transactions to "Raw Data" tab.

### Error Handling

* If sheet schema changed (user modified rows/columns) → Raise "INVALID SHEET STRUCTURE" and halt service.

---

# 6. Non-functional Requirements

## 6.1 Security

* config.json must be encrypted with Windows DPAPI.
* credentials.json stored locally must be readable only by user.
* Drive folders must be *shared with service account only* (not public).

## 6.2 Logging

`%LOCALAPPDATA%\BudgetFlow\logs\service.log`

Log levels:

* INFO: processing start/end
* WARNING: vendor not recognized
* ERROR: PDF/LLM errors
* CRITICAL: invalid sheet structure, cannot continue

## 6.3 Reliability

* Must survive network interruptions.
* Must recover after reboot automatically.
* Must ensure no duplicate processing (hash registry).

## 6.4 Performance

* Target: < 5s per PDF excluding LLM latency.
* Batch multiple PDFs in same poll cycle.

---

# 7. Technical Design

## 7.1 Folder Structure

```
budgetflow/
 ├─ src/
 │   ├─ main.py
 │   ├─ watcher/drive_watcher.py
 │   ├─ pdf/parser.py
 │   ├─ llm/processor.py
 │   ├─ sheets/manager.py
 │   ├─ utils/hash_registry.py
 │   ├─ utils/config.py
 │   ├─ utils/logger.py
 │   └─ utils/hebrew_normalizer.py
 ├─ resources/
 │   ├─ categories.json
 │   ├─ vendor_cache.json
 │   └─ sample_credentials.json
 ├─ setup/
 │   └─ setup_wizard.py
 └─ dist/
     └─ BudgetFlow.exe
```

---

# 8. Development Roadmap

### Phase 1 — Foundation

* Config system + encryption
* Logging system
* Drive + Sheets API authentication

### Phase 2 — Core Processing

* Drive polling + download
* PDF extraction
* Hebrew normalization

### Phase 3 — LLM Processor

* Prompt engineering
* Pydantic schema validation
* Category assignment

### Phase 4 — Sheets Update

* Month inference
* Category → row matching
* Additive updates
* Raw Data tab append

### Phase 5 — Robustness

* Duplicate detection
* Errors folder move
* Archive workflow

### Phase 6 — Packaging & Deployment

* PyInstaller EXE
* Background service via Task Scheduler
* Installer script

---

# 9. Risks & Mitigations Summary

| Risk                                         | Mitigation                     |
| -------------------------------------------- | ------------------------------ |
| Hebrew text reversed                         | Implement normalization module |
| PDF is scan → no text                        | Return OCR error               |
| Drive folder not shared with service account | Add check in setup wizard      |
| User changes sheet structure                 | Verify schema at startup       |
| LLM miscategorization                        | Vendor cache + fallback        |
| Duplicate uploads                            | SHA256 registry                |
| EXE silent crash                             | Daily heartbeat + log rotation |

---

# 10. Acceptance Criteria

* ✔ Setup wizard completes with all valid inputs
* ✔ Service runs 24/7 after reboot
* ✔ PDF → Text → LLM → Sheet update works end-to-end
* ✔ Duplicate PDFs are skipped
* ✔ Wrong PDFs go to Error folder
* ✔ Sheet values are additive, not overwritten
* ✔ Raw Data tab logged
* ✔ Logs show no unhandled exceptions

---

# 11. Deliverables

* Full Python source code
* Categories + vendor mapping files
* Windows EXE
* Installer + Task Scheduler config
* Troubleshooting guide
* Developer hand-off documentation

---

Data Structure (Category Mapping)
Based on your provided output.csv, here is the JSON structure the LLM must enforce.

categories.json

JSON

{
  "income": [
    "אמא",
    "אבא",
    "שכר דירה",
    "קצבת ילדים",
    "ביטוח לאומי",
    "החזר מס",
    "הפקדה",
    "פייבוקס"
  ],
  "fixed_expenses": [
    "דיור/שכר דירה",
    "חשמל",
    "ארנונה",
    "גז",
    "מים",
    "וועד בית",
    "אינטרנט/טלוויזיה",
    "טלפונים",
    "ביטוח בריאות",
    "ביטוח רכב",
    "תחזוקת הבית (הנדימן)",
    "מוצרים לבית",
    "תיקונים למוצרים"
  ],
  "variable_expenses": [
    "סופר (מזון וטואלטיקה)",
    "רכב (דלק, חניה)",
    "תחבורה ציבורית",
    "בילויים",
    "ביגוד"
  ]
}

