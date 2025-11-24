"""LLM-based transaction categorization using native Google AI."""
import re
import json
import time
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import List, Dict
from google import genai
from pydantic import BaseModel, Field, ValidationError

from .models import Transaction
from .vendor_cache import VendorCache
from utils.logger import get_logger
from utils.exceptions import LLMError, RetryableLLMError, ValidationError as BudgetValidationError

logger = get_logger()


class TransactionSchema(BaseModel):
    """Pydantic schema for transaction validation."""
    date: str = Field(description="Transaction date in DD/MM/YYYY format")
    description: str = Field(description="Transaction description")
    amount: float = Field(description="Transaction amount (negative for expenses)")
    category: str = Field(description="Transaction category")


class TransactionsResponse(BaseModel):
    """Pydantic schema for LLM response."""
    transactions: List[TransactionSchema]


class VisionCategorizer:
    """Categorizes transactions using Gemini with native Google AI SDK."""
    
    def __init__(self, api_key: str, categories_path: Path):
        """
        Initialize LLM categorizer.
        
        Args:
            api_key: Google AI API key
            categories_path: Path to categories.json
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash-lite"
        
        self.vendor_cache = VendorCache()
        self.categories = self._load_categories(categories_path)
        self.category_list = self._build_category_list()
        
        logger.info(f"Vision Categorizer initialized with {self.model_name}")
    
    def extract_transactions_from_pdf(self, pdf_path: Path, customer_id: str) -> List[Transaction]:
        """
        Extract and categorize transactions directly from PDF.
        
        Args:
            pdf_path: Path to PDF file
            customer_id: Customer identifier
            
        Returns:
            List of Transaction objects
        """
        try:
            logger.info(f"Processing PDF with Vision API: {pdf_path.name}")
            
            # Upload PDF
            logger.debug(f"Uploading {pdf_path.name}...")
            file_upload = self.client.files.upload(file=str(pdf_path))
            logger.debug(f"Uploaded: {file_upload.name}")
            
            # Wait for processing
            logger.debug("Waiting for file processing...")
            while file_upload.state.name == "PROCESSING":
                time.sleep(2)
                file_upload = self.client.files.get(name=file_upload.name)
            
            if file_upload.state.name != "ACTIVE":
                raise LLMError(f"File processing failed: {file_upload.state.name}")
            
            logger.debug("File processing complete. Generating response...")
            
            # Build prompt
            prompt = self._build_vision_prompt()
            
            # Generate content
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[file_upload, prompt]
            )
            
            if not response.text:
                raise LLMError("Vision API returned empty response")
            
            logger.info(json.dumps(response.text[:500], ensure_ascii=False))

            # Parse JSON response
            transactions_data = self._parse_response(response.text)
            
            # Convert to Transaction objects
            transactions = self._create_transactions(transactions_data, customer_id)
            
            logger.info(f"Extracted {len(transactions)} transactions from {pdf_path.name}")
            return transactions
            
        except Exception as e:
            logger.error(f"Vision extraction failed for {pdf_path.name}: {e}")
            raise RetryableLLMError(f"Failed to extract transactions: {e}")
    

    
    def _create_transactions(self, transactions_data: List[Dict], customer_id: str) -> List[Transaction]:
        """Convert parsed data to Transaction objects."""
        transactions = []
        def _parse_date_str(date_str: str) -> Optional[datetime]:
            """Try multiple common date formats and normalize two-digit years to 2000s when sensible."""
            if not date_str or not isinstance(date_str, str):
                return None

            fmt_candidates = [
                "%d/%m/%Y",
                "%d/%m/%y",
                "%Y-%m-%d",
                "%d-%m-%Y",
                "%d.%m.%Y",
                "%d.%m.%y",
                "%d %b %Y",
                "%d %b %y",
            ]

            for fmt in fmt_candidates:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # If parsed year looks like a 2-digit mapping to 1900s, and original had 2-digit year,
                    # normalize to 2000+ for reasonable recent dates (e.g., '25' -> 2025).
                    if dt.year < 1900:
                        # shouldn't normally happen, but safeguard
                        dt = dt.replace(year=dt.year + 2000)
                    # If format used %y and resulted in a year < 2000, and input had two-digit year,
                    # adjust to 2000s (covers strptime behaviour differences across environments).
                    if fmt.endswith('%y') and dt.year < 2000:
                        dt = dt.replace(year=dt.year + 2000)
                    return dt
                except Exception:
                    continue

            # Try heuristic: split by non-digits and attempt to build date
            parts = re.split(r'[^0-9]+', date_str)
            parts = [p for p in parts if p]
            if len(parts) >= 3:
                try:
                    d, m, y = parts[0], parts[1], parts[2]
                    if len(y) == 2:
                        y = '20' + y
                    dt = datetime(int(y), int(m), int(d))
                    return dt
                except Exception:
                    return None

            return None

        for txn_data in transactions_data:
            # Parse date
            date = _parse_date_str(txn_data.get("date", ""))
            if not date:
                logger.warning(f"Invalid date format: {txn_data.get('date')}, skipping transaction")
                continue
            
            # Assign category
            category = self._assign_category(
                txn_data["description"],
                txn_data["category"],
                customer_id
            )
            
            transaction = Transaction(
                date=date,
                description=txn_data.get("description", ""),
                amount=Decimal(str(txn_data.get("amount", 0.0))),
                category=category,
                raw_text=f"{txn_data.get('date', '')} {txn_data.get('description','')} {txn_data.get('amount','')}"
            )
            transactions.append(transaction)
        
        return transactions
    
    def _assign_category(self, description: str, llm_category: str, customer_id: str) -> str:
        """Assign category using vendor cache or LLM suggestion."""
        # Check vendor cache first
        cached_category = self.vendor_cache.lookup(customer_id, description)
        if cached_category:
            return cached_category
        
        # Validate LLM category
        if llm_category in self.category_list:
            # Add to cache
            self.vendor_cache.add_mapping(customer_id, description, llm_category)
            return llm_category
        
        # Fallback to "Other"
        logger.warning(f"Invalid category '{llm_category}' for '{description}', using 'Other'")
        return "Other"
    

    
    def _build_vision_prompt(self) -> str:
        """Build prompt for direct PDF processing."""
        return f"""You are a financial transaction parser for bank statements (Hebrew and English).

Analyze this PDF bank statement and extract ALL transactions.

Categories (use EXACTLY these names):
{json.dumps(self.category_list, ensure_ascii=False, indent=2)}

For each transaction, provide:
- date: DD/MM/YYYY format
- description: original description (keep Hebrew text as-is)
- amount: negative for expenses, positive for income (as a number)
- category: one of the categories above (match the Hebrew name exactly)

IMPORTANT:
- Extract ALL transactions from ALL pages
- Handle Hebrew text properly (RTL)
- Preserve original Hebrew descriptions
- Parse tables and structured data
- Identify dates in any format and convert to DD/MM/YYYY

Return ONLY a valid JSON object in this format:
{{
  "transactions": [
    {{"date": "DD/MM/YYYY", "description": "...", "amount": -123.45, "category": "..."}}
  ]
}}

Do not include any explanations or markdown formatting, just the JSON object.
*** NOTE: you should ignore credit card charges when they appears in the bank statement. ***
"""
    

    
    def _parse_response(self, response_text: str) -> List[Dict]:
        """Parse LLM JSON response."""
        try:
            # Clean response (remove markdown if present)
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                # Remove markdown code blocks
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:].strip()
            
            # Normalize smart quotes to standard double-quote
            cleaned = cleaned.replace('“', '"').replace('”', '"')

            # Remove common trailing commas before closing brackets/braces
            cleaned = re.sub(r',\s*([\]}])', r'\1', cleaned)

            # If the model wrapped JSON in text, try to extract the first JSON object/array
            json_match = re.search(r'\{.*\}|\[.*\]', cleaned, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            # Escape unescaped double quotes that appear between word characters (helps with Hebrew inner-quotes)
            cleaned = re.sub(r'(?<=[\w\u0590-\u05FF])"(?=[\w\u0590-\u05FF])', r'\\"', cleaned)

            # Parse JSON
            data = json.loads(cleaned)
            
            # Validate with Pydantic
            validated = TransactionsResponse(**data)
            
            return [txn.model_dump() for txn in validated.transactions]
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            raise LLMError(f"Invalid JSON response from LLM: {e}")
        except ValidationError as e:
            logger.error(f"Response validation failed: {e}")
            raise LLMError(f"LLM response does not match expected schema: {e}")
    
    def _load_categories(self, categories_path: Path) -> Dict:
        """Load categories from JSON file."""
        try:
            with open(categories_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise LLMError(f"Failed to load categories: {e}")
    
    def _build_category_list(self) -> List[str]:
        """Build flat list of all category names."""
        return [
            category["name"]
            for group in ["income", "fixed_expenses", "variable_expenses", "other"]
            for category in self.categories.get(group, [])
        ]
