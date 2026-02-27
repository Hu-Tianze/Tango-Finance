import requests
from decimal import Decimal
import re


TYPE_CANONICAL_MAP = {
    "income": "Income",
    "expense": "Expense",
}

INCOME_KEYWORDS = {
    "income", "salary", "bonus", "refund", "reimburse", "reimbursement", "won",
    "earn", "earned", "received", "receive", "dividend", "interest",
}

EXPENSE_KEYWORDS = {
    "expense", "spent", "spend", "buy", "bought", "pay", "paid", "cost",
    "purchase", "bill", "fee", "rent", "subscription",
}

def get_exchange_rate(from_currency, to_currency='GBP'):
    """Fetch exchange rate from Frankfurter API (no API key required)."""
    if from_currency == to_currency:
        return Decimal('1.0')
    
    try:
        url = f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            rate = data['rates'].get(to_currency)
            if rate:
                return Decimal(str(rate))
        
    except Exception as e:
        print(f"Exchange-rate API error: {e}")
    
    # Fallback rates when network is unavailable.
    fallback = {
        'CNY': Decimal('0.11'),
        'USD': Decimal('0.79'),
        'EUR': Decimal('0.84')
    }
    return fallback.get(from_currency, Decimal('1.0'))


def normalize_transaction_type(raw_type, context_text=""):
    raw = (raw_type or "").strip().lower()
    if raw in TYPE_CANONICAL_MAP:
        return TYPE_CANONICAL_MAP[raw]

    tokens = set(re.findall(r"[a-zA-Z]+", (context_text or "").lower()))
    if tokens & INCOME_KEYWORDS:
        return "Income"
    if tokens & EXPENSE_KEYWORDS:
        return "Expense"
    return "Expense"
