"""LLM-based transaction categorization."""
import json
from pathlib import Path
from datetime import datetime
from decimal import Decimal
from typing import List, Dict
from collections import Counter

from langchain.chat_models.base import init_chat_model, BaseChatModel
from pydantic import BaseModel, Field, ValidationError

from .models import Transaction
from .vendor_cache import VendorCache
from budgetflow.utils import get_logger, LLMError, RetryableLLMError, ValidationError as BudgetValidationError

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


class LLMCategorizer:
    """Categorizes transactions using Gemini Flash."""
    
    def __init__(self, api_key: str, categories_path: Path):
        """
        Initialize LLM categorizer.
        
        Args:
            api_key: Gemini API key
            categories_path: Path to categories.json
        """
        self.model: BaseChatModel = init_chat_model(
            model="gemini-1.5-flash",
            model_provider="google_genai",
            api_key=api_key,
            temperature=0.1,
            max_tokens=4096
        )
        
        self.vendor_cache = VendorCache()
        self.categories = self._load_categories(categories_path)
        self.category_list = self._build_category_list()
        
        logger.info("LLM Categorizer initialized with Gemini 1.5 Flash")
    
    def extract_transactions(self, text: str, customer_id: str) -> List[Transaction]:
        """
        Extract and categorize transactions from statement text.
        
        Args:
            text: Normalized statement text
            customer_id: Customer identifier
            
        Returns:
            List of Transaction objects
        """
        # Build prompt
        prompt = self._build_prompt(text)
        
        try:
            # Call LLM
            response = self.model.invoke(prompt)
            response_text = response.content
            
            # Parse JSON response
            transactions_data = self._parse_response(response_text)
            
            # Convert to Transaction objects and assign categories
            transactions = []
            for txn_data in transactions_data:
                # Parse date
                try:
                    date = datetime.strptime(txn_data["date"], "%d/%m/%Y")
                except ValueError:
                    logger.warning(f"Invalid date format: {txn_data['date']}, skipping transaction")
                    continue
                
                # Assign category (check cache first, then use LLM suggestion)
                category = self._assign_category(
                    txn_data["description"],
                    txn_data["category"],
                    customer_id
                )
                
                transaction = Transaction(
                    date=date,
                    description=txn_data["description"],
                    amount=Decimal(str(txn_data["amount"])),
                    category=category,
                    raw_text=f"{txn_data['date']} {txn_data['description']} {txn_data['amount']}"
                )
                transactions.append(transaction)
            
            logger.info(f"Extracted {len(transactions)} transactions for customer {customer_id}")
            return transactions
            
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            raise RetryableLLMError(f"Failed to extract transactions: {e}")
    
    def _assign_category(self, description: str, llm_category: str, customer_id: str) -> str:
        """
        Assign category using vendor cache or LLM suggestion.
        
        Args:
            description: Transaction description
            llm_category: Category suggested by LLM
            customer_id: Customer identifier
            
        Returns:
            Final category
        """
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
    
    def infer_month(self, transactions: List[Transaction]) -> int:
        """
        Infer statement month from transaction dates.
        
        Args:
            transactions: List of transactions
            
        Returns:
            Month number (1-12)
        """
        if not transactions:
            raise BudgetValidationError("Cannot infer month from empty transaction list")
        
        # Count months
        month_counts = Counter(txn.date.month for txn in transactions)
        
        # Return most common month
        most_common_month = month_counts.most_common(1)[0][0]
        logger.debug(f"Inferred month: {most_common_month}")
        return most_common_month
    
    def _build_prompt(self, text: str) -> str:
        """Build extraction prompt."""
        return f"""You are a financial transaction parser for Hebrew bank statements.

Extract all transactions from the following statement text and return a JSON object.

Categories (use EXACTLY these names):
{json.dumps(self.category_list, ensure_ascii=False, indent=2)}

For each transaction, provide:
- date: DD/MM/YYYY format
- description: original Hebrew description
- amount: negative for expenses, positive for income (as a number)
- category: one of the categories above (match the Hebrew name exactly)

Statement text:
{text}

Return ONLY a valid JSON object in this format:
{{
  "transactions": [
    {{"date": "DD/MM/YYYY", "description": "...", "amount": -123.45, "category": "..."}}
  ]
}}

Do not include any explanations or markdown formatting, just the JSON object."""
    
    def _parse_response(self, response_text: str) -> List[Dict]:
        """Parse LLM JSON response."""
        try:
            # Clean response (remove markdown if present)
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                # Remove markdown code blocks
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
            
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
        category_list = []
        
        for group in ["income", "fixed_expenses", "variable_expenses", "other"]:
            for category in self.categories.get(group, []):
                category_list.append(category["name"])
        
        return category_list
