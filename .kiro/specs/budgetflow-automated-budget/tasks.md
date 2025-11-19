# Implementation Plan

- [x] 1. Set up project structure and configuration system


  - Create directory structure for components (config, drive, pdf, llm, sheets, orchestrator, utils)
  - Implement Configuration Manager with Windows DPAPI encryption for sensitive data
  - Create config.json schema and validation logic
  - Implement setup wizard for first-time configuration (Gemini API key, service account, root folder ID, polling interval)
  - Add configuration validation for Drive and Sheets API access
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Implement logging and error handling infrastructure


  - Set up structured logging with customer context to %LOCALAPPDATA%\BudgetFlow\logs\
  - Implement log rotation (30-day retention)
  - Create custom exception classes for different error categories (ConfigError, NetworkError, PDFError, LLMError, SheetsError)
  - Implement retry decorator with exponential backoff for network operations
  - _Requirements: 7.3, 9.4_

- [x] 3. Build Hash Registry for duplicate detection


  - Create SQLite database schema at %LOCALAPPDATA%\BudgetFlow\registry.db
  - Implement HashRegistry class with methods: is_processed, mark_processed, get_customer_history
  - Add SHA256 hash calculation for PDF files
  - Create database indexes for efficient customer-hash lookups
  - _Requirements: 3.2, 3.3_

- [x] 4. Implement Google Drive integration


  - [x] 4.1 Create DrivePoller class with service account authentication


    - Initialize Google Drive API client using service account credentials
    - Implement discover_customers() to scan Root Folder for customer subfolders
    - Implement scan_customer_folder() to list PDF files in customer folder
    - _Requirements: 2.1, 3.1_


  - [ ] 4.2 Implement customer folder structure management
    - Create ensure_customer_structure() to verify/create Archive and Error subfolders
    - Implement get_or_create_subfolder() helper for subfolder management
    - Add Outputs folder verification in Root Folder
    - _Requirements: 2.2_


  - [ ] 4.3 Implement PDF file operations
    - Create download_pdf() to download files to %LOCALAPPDATA%\BudgetFlow\tmp\{customer_id}\
    - Implement move_to_archive() to move processed files
    - Implement move_to_error() for failed files
    - Add cleanup logic for temporary files
    - _Requirements: 3.4, 7.1, 7.2_



- [ ] 5. Build PDF extraction and Hebrew normalization
  - [x] 5.1 Implement PDFProcessor class

    - Create extract_text() with pdfplumber as primary extractor
    - Add pypdf as fallback extraction method
    - Implement text length validation (>100 chars for valid extraction)
    - _Requirements: 4.1, 4.2, 4.3_


  - [ ] 5.2 Create HebrewNormalizer class
    - Implement Unicode bidirectional character normalization
    - Add line direction detection and reversal for RTL text
    - Create artifact stripping logic (headers, footers, page numbers)
    - _Requirements: 4.4, 4.5_

- [x] 6. Implement LLM-based transaction categorization


  - [x] 6.1 Create LLMCategorizer class with LangChain


    - Initialize BaseChatModel using init_chat_model with Gemini 1.5 Flash
    - Configure model with temperature=0.1, max_tokens=4096
    - Create structured extraction prompt template for Hebrew statements
    - _Requirements: 5.1_

  - [x] 6.2 Implement transaction extraction and validation

    - Create Transaction dataclass with date, description, amount, category fields
    - Implement JSON schema validation using Pydantic for LLM responses
    - Add date parsing for DD/MM/YYYY format
    - Implement month inference from transaction dates (majority vote)
    - _Requirements: 5.2, 5.6_


  - [ ] 6.3 Build vendor cache system
    - Create VendorCache class with customer-specific JSON storage at %LOCALAPPDATA%\BudgetFlow\vendors\{customer_id}.json
    - Implement lookup() with exact and fuzzy matching (Levenshtein distance)
    - Add add_mapping() to update cache with new vendor-category pairs
    - Integrate vendor cache check before LLM categorization
    - _Requirements: 5.3, 5.4_


  - [ ] 6.4 Implement category assignment logic
    - Load categories.json with income, fixed_expenses, variable_expenses lists
    - Implement fallback to "Other" category for low-confidence matches
    - Add category validation against predefined list
    - _Requirements: 5.5_

- [x] 7. Create transaction aggregation module


  - Implement Aggregator class with aggregate() method
  - Group transactions by category and sum amounts
  - Create AggregatedData dataclass with customer_id, month, totals, transactions
  - _Requirements: 5.6_

- [-] 8. Build Google Sheets report generation and update system


  - [x] 8.1 Create SheetsGenerator class with Sheets API authentication

    - Initialize Google Sheets API client using service account
    - Implement get_or_create_report() to find or create customer report in Outputs folder
    - Create report naming convention: {customer_id}_Budget.xlsx
    - _Requirements: 2.3, 2.4, 6.1_

  - [x] 8.2 Implement budget sheet template and initialization

    - Create template with Budget tab (categories × months) and Raw Data tab
    - Add Category ID column (Column B) with stable identifiers
    - Implement month column headers (חודש 1 through חודש 12)
    - Populate category rows from categories.json with Hebrew names
    - _Requirements: 2.4, 6.2_


  - [ ] 8.3 Implement additive budget updates
    - Create _find_month_column() to locate month column by header text
    - Implement _find_category_row() using Category ID from Column B
    - Add logic to read existing cell value and strip currency symbols
    - Implement additive update (existing + new amount)
    - Write updated values back to cells
    - _Requirements: 6.3, 6.4, 6.5, 6.6_


  - [ ] 8.4 Implement Raw Data tab logging
    - Create append_raw_data() to log detailed transactions
    - Add columns: Date, Description, Amount, Category, Processed At
    - Append new transactions to end of Raw Data tab
    - _Requirements: 6.7_


  - [ ] 8.5 Add sheet structure validation
    - Implement validate_structure() to check for expected columns and Category IDs
    - Add critical error logging when structure is modified
    - Halt processing for affected customer only
    - _Requirements: 7.4_


  - [ ] 8.6 Set report permissions
    - Share newly created reports with service account (edit permissions)
    - Verify permissions during report creation
    - _Requirements: 2.5_

- [x] 9. Build processing orchestration and workflow



  - [x] 9.1 Create ProcessingOrchestrator class

    - Implement run_polling_cycle() to iterate through all customers
    - Create process_customer() to handle single customer workflow
    - Implement process_pdf() for individual file processing
    - _Requirements: 3.1, 8.2_

  - [x] 9.2 Implement end-to-end processing pipeline

    - Integrate all components: DrivePoller → PDFProcessor → HebrewNormalizer → LLMCategorizer → Aggregator → SheetsGenerator
    - Add customer context propagation through pipeline
    - Implement file state transitions (download → process → archive/error)
    - Add hash registry updates after successful/failed processing
    - _Requirements: 3.4, 3.5, 7.1, 7.2_

  - [x] 9.3 Implement error isolation between customers

    - Wrap customer processing in try-except to prevent cascading failures
    - Log errors with customer context
    - Continue processing remaining customers after individual failures
    - _Requirements: 7.4, 8.3_

  - [x] 9.4 Add concurrent customer processing

    - Implement ThreadPoolExecutor for parallel customer processing
    - Add configurable max_concurrent_customers limit
    - Ensure thread-safe access to shared resources (logs, database)

    - _Requirements: 8.2_

- [-] 10. Implement Windows service and scheduling

  - [x] 10.1 Create main service loop

    - Implement infinite polling loop with configurable interval
    - Add graceful shutdown handling (SIGTERM, SIGINT)
    - Implement heartbeat logging every cycle
    - _Requirements: 8.1, 8.2_

  - [x] 10.2 Add network resilience

    - Implement retry logic for network interruptions
    - Add connection health checks before processing
    - Resume from last known state using Hash Registry
    - _Requirements: 8.3, 8.4_


  - [ ] 10.3 Create Windows Task Scheduler integration
    - Generate Task Scheduler XML configuration
    - Set trigger: At system startup
    - Configure: Run whether user is logged on or not, highest privileges
    - Add restart on failure (3 attempts, 1 minute interval)
    - _Requirements: 8.1_


- [-] 11. Package application as Windows executable

  - [x] 11.1 Create PyInstaller configuration

    - Write .spec file for BudgetFlow.exe
    - Include all dependencies (google-api-python-client, langchain, pdfplumber, pypdf)
    - Bundle resources (categories.json template)
    - Set icon and version info
    - _Requirements: 9.1_

  - [x] 11.2 Create installer script

    - Build setup wizard executable
    - Copy EXE to Program Files
    - Create AppData directories
    - Register with Task Scheduler
    - _Requirements: 9.1_


- [-] 12. Create test suite

  - [x] 12.1 Write unit tests for core components

    - Test ConfigManager encryption/decryption
    - Test PDFProcessor with sample Hebrew PDFs
    - Test HebrewNormalizer with various text samples
    - Test Aggregator calculations
    - Test HashRegistry database operations
    - _Requirements: All_


  - [ ] 12.2 Create integration tests
    - Test end-to-end flow with mock Drive and Sheets APIs
    - Test multi-customer concurrent processing
    - Test error handling and recovery scenarios
    - Test duplicate detection workflow
    - _Requirements: All_


  - [ ] 12.3 Add LLM categorization tests
    - Create mock LLM responses for testing
    - Test category assignment logic
    - Test vendor cache lookup and updates
    - Test fallback to "Other" category
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 13. Create documentation and deployment guide




  - [x] 13.1 Write user documentation

    - Create setup guide with screenshots
    - Document folder structure requirements
    - Add troubleshooting section
    - Create FAQ for common issues
    - _Requirements: All_

  - [x] 13.2 Write developer documentation

    - Document architecture and component interactions
    - Add API reference for each class
    - Create contribution guidelines
    - Document deployment process
    - _Requirements: All_
