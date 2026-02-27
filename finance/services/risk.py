import json
import logging
import os
from decimal import Decimal
from statistics import mean

import requests
from django.db import transaction
from django.utils import timezone

from finance.models import RiskAlert, Transaction

logger = logging.getLogger(__name__)


def _level_from_score(score):
    if score >= 75:
        return "HIGH"
    if score >= 45:
        return "MEDIUM"
    return "LOW"


def _heuristic_risk(transaction_obj):
    # Risk warnings are only meaningful for expenses.
    if transaction_obj.type != "Expense":
        return {"score": Decimal("0"), "level": "LOW", "reason": "Non-expense transaction", "source": "HEURISTIC"}

    score = Decimal("0")
    reasons = []

    current_amount = Decimal(str(transaction_obj.amount_in_gbp or 0))
    if current_amount >= Decimal("100"):
        score += Decimal("20")
        reasons.append("High absolute amount.")

    thirty_days_ago = timezone.now() - timezone.timedelta(days=30)
    recent_expenses = Transaction.objects.filter(
        user=transaction_obj.user,
        type="Expense",
        occurred_at__gte=thirty_days_ago,
    ).exclude(id=transaction_obj.id)

    expense_amounts = [Decimal(str(v)) for v in recent_expenses.values_list("amount_in_gbp", flat=True) if v is not None]
    if expense_amounts:
        avg_amount = Decimal(str(mean(expense_amounts)))
        if avg_amount > 0 and current_amount > avg_amount * Decimal("3"):
            score += Decimal("35")
            reasons.append("Much larger than your 30-day average expense.")

    if transaction_obj.currency != "GBP":
        score += Decimal("8")
        reasons.append("Cross-currency transaction.")

    hour = transaction_obj.occurred_at.hour if transaction_obj.occurred_at else None
    if hour is not None and (hour <= 5 or hour >= 23):
        score += Decimal("10")
        reasons.append("Transaction happened at unusual time.")

    note_text = (transaction_obj.note or "").lower()
    if any(k in note_text for k in ["gift card", "crypto", "wire", "unknown", "atm", "cash out"]):
        score += Decimal("18")
        reasons.append("Contains high-risk keyword pattern.")

    score = min(score, Decimal("100"))
    level = _level_from_score(score)
    reason = " ".join(reasons) if reasons else "No obvious anomaly pattern."
    return {"score": score, "level": level, "reason": reason, "source": "HEURISTIC"}


def _llm_risk(transaction_obj, heuristic_result):
    if os.getenv("ENABLE_LLM_RISK", "False") != "True":
        return None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    # Keep token/cost low: only ask LLM on potentially suspicious expenses.
    if heuristic_result["score"] < Decimal("35") or transaction_obj.type != "Expense":
        return None

    recent = list(
        Transaction.objects.filter(user=transaction_obj.user, type="Expense")
        .order_by("-occurred_at")
        .values("amount_in_gbp", "currency", "category__name", "note", "occurred_at")[:8]
    )

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a fintech risk assistant. Classify suspicious spending risk."
                    " Return strict JSON with keys: risk_level (LOW|MEDIUM|HIGH),"
                    " risk_score (0-100), reason (short)."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "transaction": {
                            "amount_in_gbp": str(transaction_obj.amount_in_gbp),
                            "currency": transaction_obj.currency,
                            "category": transaction_obj.category.name if transaction_obj.category else "General",
                            "note": transaction_obj.note or "",
                            "occurred_at": str(transaction_obj.occurred_at),
                        },
                        "recent_expenses": recent,
                        "heuristic": {
                            "risk_score": str(heuristic_result["score"]),
                            "risk_level": heuristic_result["level"],
                            "reason": heuristic_result["reason"],
                        },
                    },
                    default=str,
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        llm = json.loads(content)
        score = Decimal(str(llm.get("risk_score", heuristic_result["score"])))
        score = max(Decimal("0"), min(score, Decimal("100")))
        level = llm.get("risk_level", _level_from_score(score))
        if level not in {"LOW", "MEDIUM", "HIGH"}:
            level = _level_from_score(score)
        reason = llm.get("reason", heuristic_result["reason"])
        return {"score": score, "level": level, "reason": reason, "source": "HYBRID"}
    except Exception:
        logger.exception("LLM risk scoring failed for transaction_id=%s", transaction_obj.id)
        return None


@transaction.atomic
def evaluate_and_persist_risk_alert(transaction_obj):
    heuristic = _heuristic_risk(transaction_obj)
    llm_result = _llm_risk(transaction_obj, heuristic)
    final = llm_result or heuristic

    if final["level"] == "LOW":
        # Keep existing alert history but mark as resolved when risk drops.
        RiskAlert.objects.filter(transaction=transaction_obj, status="OPEN").update(
            status="RESOLVED",
            updated_at=timezone.now(),
            reason=final["reason"],
            risk_score=final["score"],
            risk_level=final["level"],
            source=final["source"],
        )
        return None

    alert, _ = RiskAlert.objects.update_or_create(
        transaction=transaction_obj,
        defaults={
            "user": transaction_obj.user,
            "risk_level": final["level"],
            "risk_score": final["score"],
            "reason": final["reason"],
            "source": final["source"],
            "status": "OPEN",
        },
    )
    return alert
