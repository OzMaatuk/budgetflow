# Requirements Document

## Introduction

BudgetFlow is an automated finance-processing system that runs locally on Windows PC. The system monitors a structured Google Drive folder hierarchy containing customer-specific subfolders for uploaded PDF bank/credit card statements. It extracts transaction data, categorizes transactions using AI, and automatically generates or updates customer-specific Google Sheets budget reports in a dedicated outputs folder. The system supports multiple customers with isolated processing, zero-manual-entry budget tracking, seamless mobile upload capability, and local-only sensitive data processing.

## Glossary

- **BudgetFlow System**: The complete automated budget processing application running as a Windows service
- **Drive Poller**: Component that monitors Google Drive customer folders for new PDF files
- **PDF Processor**: Component that extracts text content from PDF bank statements
- **LLM Categorizer**: AI-powered component using Gemini Flash to categorize transactions
- **Sheets Generator**: Component that creates or updates customer-specific Google Sheets budget reports
- **Root Folder**: Top-level Google Drive folder containing all BudgetFlow data
- **Customer Folder**: Subfolder within Root Folder dedicated to a specific customer's input documents
- **Outputs Folder**: Subfolder within Root Folder containing generated budget reports for all customers
- **Archive Subfolder**: Subfolder within each Customer Folder where successfully processed PDFs are moved
- **Error Subfolder**: Subfolder within each Customer Folder where failed PDFs are moved
- **Customer Report**: Google Sheets file in Outputs Folder containing budget data for a specific customer
- **Raw Data Tab**: Google Sheets tab within Customer Report containing detailed transaction logs
- **Service Account**: Google Cloud service account used for API authentication
- **Hash Registry**: Local database tracking processed files by SHA256 hash per customer
- **Customer Identifier**: Unique name or ID used to identify customer folders and associate reports

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want to configure BudgetFlow with a multi-customer folder structure, so that multiple customers can use the system with isolated data

#### Acceptance Criteria

1. WHEN the BudgetFlow System starts for the first time, THE BudgetFlow System SHALL display a setup wizard requesting Gemini API key, Google Service Account credentials file, Root Folder ID in Google Drive, and polling frequency
2. WHEN the setup wizard receives all required inputs, THE BudgetFlow System SHALL validate API access to Google Drive and Google Sheets before saving configuration
3. WHEN the setup wizard validates Root Folder access successfully, THE BudgetFlow System SHALL verify or create an Outputs Folder within the Root Folder
4. WHEN the setup wizard validates configuration successfully, THE BudgetFlow System SHALL encrypt and save settings to local AppData directory using Windows DPAPI
5. WHEN the setup wizard detects invalid credentials or inaccessible resources, THE BudgetFlow System SHALL display specific error messages indicating which validation failed

### Requirement 2

**User Story:** As a system administrator, I want to add new customers by creating folders, so that the system automatically processes their statements without code changes

#### Acceptance Criteria

1. WHEN a new folder is created within the Root Folder with a valid Customer Identifier name, THE BudgetFlow System SHALL recognize it as a Customer Folder during the next polling cycle
2. WHEN the BudgetFlow System detects a new Customer Folder, THE BudgetFlow System SHALL create Archive Subfolder and Error Subfolder within that Customer Folder
3. WHEN the BudgetFlow System detects a new Customer Folder, THE BudgetFlow System SHALL create a new Customer Report in the Outputs Folder with the customer name in the filename
4. WHEN the BudgetFlow System creates a new Customer Report, THE BudgetFlow System SHALL initialize the report with predefined budget structure including category rows and month columns
5. WHEN the BudgetFlow System creates a new Customer Report, THE BudgetFlow System SHALL share the report with the Service Account with edit permissions

### Requirement 3

**User Story:** As a budget user, I want to upload PDF statements to my dedicated customer folder, so that my budget updates automatically without affecting other customers

#### Acceptance Criteria

1. WHEN the BudgetFlow System is running, THE Drive Poller SHALL scan all Customer Folders within the Root Folder for new PDF files at the configured polling interval
2. WHEN the Drive Poller detects a PDF file in a Customer Folder, THE Drive Poller SHALL calculate the file's SHA256 hash and compare it against the Hash Registry for that customer
3. IF the PDF file hash exists in the Hash Registry for that customer, THEN THE Drive Poller SHALL move the file to the customer's Duplicates subfolder without processing
4. WHEN the Drive Poller identifies a new unprocessed PDF file in a Customer Folder, THE Drive Poller SHALL download the file to local temporary storage with customer context
5. WHEN the Drive Poller completes downloading a PDF file, THE Drive Poller SHALL mark the file as processing in the local database with associated Customer Identifier

### Requirement 4

**User Story:** As a budget user, I want Hebrew bank statements to be processed correctly, so that all my transactions are captured accurately

#### Acceptance Criteria

1. WHEN the PDF Processor receives a downloaded PDF file with customer context, THE PDF Processor SHALL extract text content using pdfplumber library
2. IF pdfplumber extraction fails, THEN THE PDF Processor SHALL attempt extraction using pypdf library as fallback
3. WHEN the PDF Processor extracts text with length less than 100 characters, THE PDF Processor SHALL log an OCR-unsupported error and move the file to the customer's Error Subfolder
4. WHEN the PDF Processor extracts Hebrew text content, THE PDF Processor SHALL normalize Unicode bidirectional characters and reverse line direction if needed
5. WHEN the PDF Processor completes text extraction successfully, THE PDF Processor SHALL pass the normalized text with customer context to the LLM Categorizer

### Requirement 5

**User Story:** As a budget user, I want transactions automatically categorized into my budget categories, so that I can see spending breakdown without manual classification

#### Acceptance Criteria

1. WHEN the LLM Categorizer receives normalized statement text with customer context, THE LLM Categorizer SHALL send the text to Gemini Flash API with a structured extraction prompt
2. WHEN the LLM Categorizer receives API response, THE LLM Categorizer SHALL validate the response against a predefined JSON schema containing date, description, amount, and category fields
3. WHEN the LLM Categorizer assigns a category to a transaction, THE LLM Categorizer SHALL first check the customer-specific vendor cache lookup file for matching vendor names
4. IF the vendor is not found in customer cache, THEN THE LLM Categorizer SHALL use Gemini Flash to determine the appropriate category from the predefined category list
5. IF the LLM Categorizer cannot determine a category with confidence, THEN THE LLM Categorizer SHALL assign the transaction to the "Other" category
6. WHEN the LLM Categorizer completes processing all transactions, THE LLM Categorizer SHALL infer the statement month from the majority of transaction dates

### Requirement 6

**User Story:** As a budget user, I want my customer-specific Google Sheets budget to update automatically with new transactions, so that I always see current totals

#### Acceptance Criteria

1. WHEN the Sheets Generator receives categorized transactions with customer context for a specific month, THE Sheets Generator SHALL locate the Customer Report in the Outputs Folder matching the Customer Identifier
2. WHEN the Sheets Generator locates the Customer Report, THE Sheets Generator SHALL find the corresponding month column in the sheet by matching header text
3. WHEN the Sheets Generator processes a transaction category, THE Sheets Generator SHALL locate the category row using the internal category ID from column B
4. WHEN the Sheets Generator locates the target cell, THE Sheets Generator SHALL fetch the existing numeric value and remove currency symbols and formatting
5. WHEN the Sheets Generator calculates the new value, THE Sheets Generator SHALL add the transaction amount to the existing value rather than overwriting
6. WHEN the Sheets Generator completes category aggregation, THE Sheets Generator SHALL write all updated values back to the Customer Report
7. WHEN the Sheets Generator finishes updating budget totals, THE Sheets Generator SHALL append detailed transaction records to the Raw Data Tab in the Customer Report

### Requirement 7

**User Story:** As a budget user, I want processed statements archived and errors handled gracefully, so that I can audit the system and troubleshoot issues

#### Acceptance Criteria

1. WHEN the BudgetFlow System completes processing a PDF file successfully, THE BudgetFlow System SHALL move the file from the Customer Folder to the customer's Archive Subfolder in Google Drive
2. IF the PDF Processor or LLM Categorizer encounters an error during processing, THEN THE BudgetFlow System SHALL move the file to the customer's Error Subfolder in Google Drive
3. WHEN the BudgetFlow System performs any processing operation, THE BudgetFlow System SHALL write log entries with appropriate severity levels to the local log file including Customer Identifier context
4. WHEN the BudgetFlow System detects that a Customer Report structure has been modified, THE BudgetFlow System SHALL log a critical error and halt processing for that customer only while continuing to process other customers

### Requirement 8

**User Story:** As a budget user, I want the system to run continuously in the background, so that statements are processed automatically without my intervention

#### Acceptance Criteria

1. WHEN the Windows operating system starts, THE BudgetFlow System SHALL launch automatically via Windows Task Scheduler
2. WHILE the BudgetFlow System is running, THE BudgetFlow System SHALL continue polling all Customer Folders and processing without requiring user interaction
3. WHEN the BudgetFlow System encounters a network interruption, THE BudgetFlow System SHALL retry the failed operation and continue processing
4. WHEN the BudgetFlow System restarts after a system reboot, THE BudgetFlow System SHALL resume processing from the last known state using the Hash Registry for each customer

### Requirement 9

**User Story:** As a budget user, I want my financial data secured locally, so that sensitive information is not exposed

#### Acceptance Criteria

1. WHEN the BudgetFlow System stores configuration data, THE BudgetFlow System SHALL encrypt the configuration file using Windows DPAPI
2. WHEN the BudgetFlow System stores Google Service Account credentials, THE BudgetFlow System SHALL set file permissions to be readable only by the current user
3. WHEN the BudgetFlow System shares Google Drive folders, THE BudgetFlow System SHALL verify during setup that the Root Folder is shared only with the Service Account and not publicly accessible
4. WHEN the BudgetFlow System processes PDF files, THE BudgetFlow System SHALL store temporary files in the user's local AppData directory with customer-specific subdirectories and delete them after processing
5. WHEN the BudgetFlow System creates Customer Reports, THE BudgetFlow System SHALL ensure each report is isolated and accessible only through the Service Account

### Requirement 10

**User Story:** As a system administrator, I want the ability to view all customer reports in one location, so that I can monitor system activity and customer budgets

#### Acceptance Criteria

1. WHEN the BudgetFlow System creates or updates Customer Reports, THE BudgetFlow System SHALL store all reports in the Outputs Folder within the Root Folder
2. WHEN the BudgetFlow System names a Customer Report file, THE BudgetFlow System SHALL use a consistent naming convention including the Customer Identifier
3. WHEN a user accesses the Outputs Folder, THE user SHALL see all Customer Reports organized in a single location
4. WHEN the BudgetFlow System processes statements for a customer, THE BudgetFlow System SHALL update only that customer's report without affecting other Customer Reports
