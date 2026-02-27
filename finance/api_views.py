import requests
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from .models import Transaction
from django.db import transaction, models
from django.utils import timezone
from datetime import timedelta
import os
import logging
from .services import create_transaction

logger = logging.getLogger(__name__)


class AgentTransactionAPI(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        try:
            with transaction.atomic():
                amount_val = data.get('amount')
                if not amount_val:
                    return Response({"status": "error", "message": "Amount is required"}, status=400)
                
                cat_name = data.get('category', 'General').strip()
                new_tx = create_transaction(
                    user=request.user,
                    amount=amount_val,
                    currency=data.get('currency', 'GBP'),
                    tx_type=data.get('type', 'Expense'),
                    note=data.get('note', ''),
                    note_prefix='[AI Agent] ',
                    occurred_at=data.get('date') or timezone.now(),
                    category_name=cat_name,
                    type_context=f"{data.get('note', '')} {cat_name}",
                )
                return Response({"status": "success", "transaction_id": new_tx.id})
        except ValueError:
            return Response({"status": "error", "message": "Invalid amount format"}, status=400)
        except Exception:
            logger.exception("Agent transaction create failed for user_id=%s", request.user.id)
            return Response({"status": "error", "message": "Internal server error"}, status=500)

class ChatAgentAPI(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_query = request.data.get('query', '').strip()
        if not user_query:
            return Response({"error": "Query cannot be empty"}, status=400)

        API_KEY = os.getenv("GROQ_API_KEY") 
        
        if not API_KEY:
            return Response({"error": "GROQ_API_KEY not found in environment variables"}, status=500)
        BASE_URL = "https://api.groq.com/openai/v1/chat/completions" 
        MODEL_NAME = "llama-3.1-8b-instant"

        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_txs = Transaction.objects.filter(user=request.user, occurred_at__gte=thirty_days_ago)
        stats = recent_txs.values('type').annotate(total=models.Sum('amount_in_gbp'))
        
        last_5 = recent_txs.order_by('-occurred_at')[:5]
        history_str = "\n".join([f"- {t.occurred_at.date()}: {t.amount_in_gbp} GBP ({t.category.name if t.category else 'General'})" for t in last_5])

        system_prompt = f"""
        You are a smart financial assistant. 
        User's 30-day memory stats: {list(stats)}.
        Recent history:
        {history_str}

        TASK:
        1. If recording a transaction, return JSON: {{"action": "record", "data": {{"amount": 10.5, "currency": "GBP", "category": "Food", "type": "Expense", "note": "..."}}}}
        2. If analyzing/chatting, return JSON: {{"action": "chat", "analysis": "Your reply here..."}}
        3. ALWAYS return valid JSON.
        """

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            "response_format": {"type": "json_object"},
            "stream": False
        }
        headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

        try:
            response = requests.post(BASE_URL, json=payload, headers=headers, timeout=20)
            response.raise_for_status()
            res_json = response.json()
            ai_content = res_json['choices'][0]['message']['content']
            ai_data = json.loads(ai_content)

            if ai_data.get('action') == 'record':
                record_data = ai_data.get('data')
                with transaction.atomic():
                    cat_name = record_data.get('category', 'General')
                    new_tx = create_transaction(
                        user=request.user,
                        amount=record_data.get('amount'),
                        currency=record_data.get('currency', 'GBP'),
                        tx_type=record_data.get('type', 'Expense'),
                        note=record_data.get('note', ''),
                        note_prefix='[AI Chat] ',
                        occurred_at=record_data.get('date') or timezone.now(),
                        category_name=cat_name,
                        type_context=f"{user_query} {record_data.get('note', '')} {cat_name}",
                    )
                return Response({
                    "type": "record", 
                    "message": f"Got it! I've recorded £{new_tx.original_amount} under {cat_name}."
                })
            else:
                return Response({
                    "type": "analysis", 
                    "message": ai_data.get('analysis', "I couldn't process that.")
                })

        except Exception:
            logger.exception("Chat agent failed for user_id=%s", request.user.id)
            return Response({"error": "Internal server error"}, status=500)
