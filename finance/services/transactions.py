from decimal import Decimal, InvalidOperation

from django.utils import timezone

from finance.models import Category, Transaction
from finance.utils import normalize_transaction_type


def _normalize_amount(amount):
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid amount format") from exc
    if value <= 0:
        raise ValueError("Amount must be positive")
    return value


def get_or_create_category_for_user(user, category_name):
    name = (category_name or "").strip() or "General"
    return Category.objects.get_or_create(
        user=user,
        name=name,
        defaults={"type_scope": "Expense"},
    )[0]


def create_transaction(
    *,
    user,
    amount,
    currency="GBP",
    tx_type="Expense",
    note="",
    occurred_at=None,
    category=None,
    category_name=None,
    note_prefix="",
    type_context="",
):
    normalized_amount = _normalize_amount(amount)
    final_category = category or (
        get_or_create_category_for_user(user, category_name) if category_name is not None else None
    )
    final_note = f"{note_prefix}{note or ''}".strip()
    normalized_type = normalize_transaction_type(tx_type, type_context or final_note)

    return Transaction.objects.create(
        user=user,
        category=final_category,
        original_amount=normalized_amount,
        currency=currency or "GBP",
        type=normalized_type,
        note=final_note[:200],
        occurred_at=occurred_at or timezone.now(),
    )


def update_transaction(
    *,
    tx,
    amount,
    currency,
    tx_type,
    note,
    occurred_at,
    category,
):
    tx.original_amount = _normalize_amount(amount)
    tx.currency = currency or "GBP"
    tx.type = normalize_transaction_type(tx_type, note or "")
    tx.note = (note or "")[:200]
    tx.occurred_at = occurred_at or timezone.now()
    tx.category = category
    tx.save()
    return tx

