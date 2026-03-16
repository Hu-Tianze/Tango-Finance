from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.db.models import Sum
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth import login as auth_login, authenticate, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone  
from django.core.cache import cache  
from django.core.mail import send_mail
from django.db import transaction
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.paginator import Paginator
from contextlib import nullcontext
import logging
import secrets
import csv
import json
import smtplib
import requests
from datetime import date, timedelta
import hashlib
from decimal import Decimal, InvalidOperation

User = get_user_model()
from .models import Transaction, Category
from .services import create_transaction, update_transaction
from .constants import (
    CURRENCY_CODES,
    PROFILE_TIMEZONE_CHOICES,
    STARTER_EXPENSE_CATEGORIES,
    OTP_RATE_LIMIT_SECONDS,
    OTP_REGISTER_TTL_SECONDS,
    OTP_ACCOUNT_ACTION_TTL_SECONDS,
    TURNSTILE_VERIFY_TIMEOUT_SECONDS,
    ASSISTANT_NAME,
    TRANSACTION_PAGE_SIZE,
)
from .navigation import get_site_search_items
from user.models import EmailOTP as UserEmailOTP

CF_SECRET_KEY = settings.CF_TURNSTILE_SECRET_KEY
CF_SITE_KEY = settings.CF_TURNSTILE_SITE_KEY
TURNSTILE_ENABLED = getattr(settings, "TURNSTILE_ENABLED", True)
logger = logging.getLogger(__name__)


@login_required
def signout_view(request):
    auth_logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("login")

def verify_turnstile(token, ip):
    if settings.DEBUG:
        return True
    if not TURNSTILE_ENABLED:
        return True
    if not token or not CF_SECRET_KEY:
        return False
    try:
        response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={'secret': CF_SECRET_KEY, 'response': token, 'remoteip': ip},
            timeout=TURNSTILE_VERIFY_TIMEOUT_SECONDS
        )
        return response.json().get('success', False)
    except requests.RequestException:
        logger.exception("Turnstile verification request failed")
        return False


def _send_otp_email(*, recipient, code, purpose, ttl_seconds):
    app_name = "Tango Finance"
    purpose_labels = {
        "register": "account registration",
        "delete_account": "account deletion confirmation",
        "change_password": "password change confirmation",
    }
    purpose_text = purpose_labels.get(purpose, "verification")
    subject = f"{app_name} verification code"
    body = (
        f"Your {app_name} code for {purpose_text} is: {code}\n\n"
        f"This code will expire in {ttl_seconds // 60} minutes.\n"
        "If you did not request this, please ignore this email."
    )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        fail_silently=False,
    )


def _ensure_starter_categories(user):
    if Category.objects.filter(user=user).exists():
        return
    for cat_name in STARTER_EXPENSE_CATEGORIES:
        Category.objects.get_or_create(user=user, name=cat_name, type_scope='Expense')


def _parse_transaction_filters(request):
    return {
        "q": (request.GET.get("q") or "").strip(),
        "date_from": (request.GET.get("date_from") or "").strip(),
        "date_to": (request.GET.get("date_to") or "").strip(),
        "min_amount": (request.GET.get("min_amount") or "").strip(),
        "max_amount": (request.GET.get("max_amount") or "").strip(),
        "sort": (request.GET.get("sort") or "newest").strip(),
    }


def _sort_key(sort):
    sort_map = {
        "newest": "-occurred_at",
        "oldest": "occurred_at",
        "amount_desc": "-original_amount",
        "amount_asc": "original_amount",
        "settlement_desc": "-amount_in_gbp",
        "settlement_asc": "amount_in_gbp",
    }
    return sort_map.get(sort, "-occurred_at")


def _apply_transaction_filters(queryset, filters, request):
    items = queryset
    query_text = filters["q"]
    if query_text:
        items = items.filter(
            Q(note__icontains=query_text)
            | Q(category__name__icontains=query_text)
            | Q(type__icontains=query_text)
            | Q(currency__icontains=query_text)
        )

    if filters["date_from"]:
        items = items.filter(occurred_at__date__gte=filters["date_from"])
    if filters["date_to"]:
        items = items.filter(occurred_at__date__lte=filters["date_to"])

    try:
        if filters["min_amount"]:
            items = items.filter(original_amount__gte=Decimal(filters["min_amount"]))
    except InvalidOperation:
        messages.warning(request, "Minimum amount filter was invalid and has been ignored.")

    try:
        if filters["max_amount"]:
            items = items.filter(original_amount__lte=Decimal(filters["max_amount"]))
    except InvalidOperation:
        messages.warning(request, "Maximum amount filter was invalid and has been ignored.")

    return items.order_by(_sort_key(filters["sort"]))


def _build_behavior_insights(base_items):
    now = timezone.now()
    current_30_start = now - timedelta(days=30)
    previous_30_start = now - timedelta(days=60)

    current_30_expense_qs = base_items.filter(type="Expense", occurred_at__gte=current_30_start)
    previous_30_expense_qs = base_items.filter(
        type="Expense",
        occurred_at__gte=previous_30_start,
        occurred_at__lt=current_30_start,
    )

    current_30_expense = current_30_expense_qs.aggregate(total=Sum("amount_in_gbp"))["total"] or Decimal("0")
    previous_30_expense = previous_30_expense_qs.aggregate(total=Sum("amount_in_gbp"))["total"] or Decimal("0")

    top_category_row = (
        current_30_expense_qs.values("category__name")
        .annotate(total=Sum("amount_in_gbp"))
        .order_by("-total")
        .first()
    )

    biggest_expense = current_30_expense_qs.order_by("-amount_in_gbp").first()
    trend_direction = "steady"
    trend_percent = Decimal("0")
    if previous_30_expense > 0:
        trend_percent = ((current_30_expense - previous_30_expense) / previous_30_expense) * Decimal("100")
        if trend_percent > 0:
            trend_direction = "up"
        elif trend_percent < 0:
            trend_direction = "down"
    elif current_30_expense > 0:
        trend_direction = "up"
        trend_percent = Decimal("100")

    return {
        "avg_daily_expense": current_30_expense / Decimal("30"),
        "current_30_expense": current_30_expense,
        "previous_30_expense": previous_30_expense,
        "top_category_name": (top_category_row or {}).get("category__name") or "General",
        "top_category_total": (top_category_row or {}).get("total") or Decimal("0"),
        "largest_expense_amount": biggest_expense.amount_in_gbp if biggest_expense else Decimal("0"),
        "largest_expense_label": biggest_expense.category.name if biggest_expense and biggest_expense.category else "General",
        "trend_direction": trend_direction,
        "trend_percent": trend_percent,
    }


def _build_query_without_page(request):
    query = request.GET.copy()
    query.pop("page", None)
    return query.urlencode()


def _build_dashboard_visuals(base_items, month_income, month_expense):
    total_flow = month_income + month_expense
    if total_flow > 0:
        expense_progress = float((month_expense / total_flow) * Decimal("100"))
        income_progress = float((month_income / total_flow) * Decimal("100"))
    else:
        expense_progress = 0.0
        income_progress = 0.0

    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=29)
    daily_rows = (
        base_items.filter(
            type="Expense",
            occurred_at__date__gte=start_date,
            occurred_at__date__lte=end_date,
        )
        .values("occurred_at__date")
        .annotate(total=Sum("amount_in_gbp"))
    )
    expense_by_day = {
        row["occurred_at__date"]: row.get("total") or Decimal("0")
        for row in daily_rows
    }

    bucket_totals = []
    for bucket_idx in range(5):
        bucket_start = start_date + timedelta(days=bucket_idx * 6)
        bucket_end = min(end_date, bucket_start + timedelta(days=5))
        current_day = bucket_start
        bucket_total = Decimal("0")
        while current_day <= bucket_end:
            bucket_total += expense_by_day.get(current_day, Decimal("0"))
            current_day += timedelta(days=1)
        bucket_totals.append(bucket_total)

    peak_bucket = max(bucket_totals) if bucket_totals else Decimal("0")
    focus_bar_heights = []
    for bucket_total in bucket_totals:
        if peak_bucket <= 0 or bucket_total <= 0:
            focus_bar_heights.append(0.0)
            continue
        scaled_height = float((bucket_total / peak_bucket) * Decimal("100"))
        # Keep non-zero bars visible while still data-driven.
        focus_bar_heights.append(max(12.0, round(scaled_height, 1)))

    return {
        "expense_progress": round(expense_progress, 1),
        "income_progress": round(income_progress, 1),
        "focus_bar_heights": focus_bar_heights,
    }


def _build_fallback_spending_summary(behavior_insights):
    direction_map = {
        "up": "up compared with the previous 30 days",
        "down": "down compared with the previous 30 days",
        "steady": "stable compared with the previous 30 days",
    }
    return (
        f"Your top spending category is {behavior_insights['top_category_name']} "
        f"(£{behavior_insights['top_category_total']:.2f}) in the last 30 days. "
        f"Overall spending is {direction_map.get(behavior_insights['trend_direction'], 'stable')}."
    )


def _build_spending_summary(user, base_items, behavior_insights):
    fallback = _build_fallback_spending_summary(behavior_insights)
    api_key = settings.GROQ_API_KEY
    if not api_key:
        return fallback, "Rules-based"

    latest_tx = base_items.order_by("-occurred_at").values_list("occurred_at", flat=True).first()
    latest_marker = int(latest_tx.timestamp()) if latest_tx else 0
    cache_key = f"finance:llm_spending_summary:{user.id}:{latest_marker}"
    cached = cache.get(cache_key)
    if cached:
        return cached, "LLM"

    category_rows = (
        base_items.filter(type="Expense", occurred_at__gte=timezone.now() - timedelta(days=30))
        .values("category__name")
        .annotate(total=Sum("amount_in_gbp"))
        .order_by("-total")[:5]
    )
    top_categories = [
        f"{row.get('category__name') or 'General'}: £{(row.get('total') or Decimal('0')):.2f}"
        for row in category_rows
    ]
    prompt = (
        "Write a concise spending summary in 2 short sentences for the user.\n"
        f"Top categories last 30d: {top_categories or ['No expense records']}.\n"
        f"Largest expense category: {behavior_insights['largest_expense_label']}.\n"
        f"Trend percent: {behavior_insights['trend_percent']:.1f}% ({behavior_insights['trend_direction']}).\n"
        "Tone: practical and neutral. No markdown."
    )
    payload = {
        "model": settings.AI_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": "You are a fintech insights assistant."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "max_tokens": 120,
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            settings.AI_API_BASE_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
        summary = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        if not summary:
            return fallback, "Rules-based"
        cache.set(cache_key, summary, timeout=900)
        return summary, "LLM"
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError):
        logger.exception("Failed to build LLM spending summary for user_id=%s", user.id)
        return fallback, "Rules-based"

def register(request):
    register_form = {
        "email": "",
        "name": "",
        "code": "",
    }
    context = {
        "turnstile_site_key": CF_SITE_KEY,
        "turnstile_enabled": TURNSTILE_ENABLED,
        "register_form": register_form,
    }
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        nickname = request.POST.get('name')
        password = request.POST.get('password')
        code_input = request.POST.get('code')
        register_form.update({
            "email": email,
            "name": (nickname or "").strip(),
            "code": (code_input or "").strip(),
        })

        try:
            validate_email(email)
        except ValidationError:
            messages.error(request, "Invalid email address.")
            return render(request, 'registration/register.html', context)

        attempt_key = f"finance:reg_otp_attempts:{email}"
        attempts = cache.get(attempt_key, 0)
        if attempts >= 5:
            messages.error(request, "Too many failed attempts. Please request a new code.")
            return render(request, 'registration/register.html', context)

        otp_key = f"finance:reg_otp:{email}"
        stored_hash = cache.get(otp_key)
        input_hash = hashlib.sha256((code_input or "").encode("utf-8")).hexdigest()

        if not stored_hash or input_hash != stored_hash:
            cache.set(attempt_key, attempts + 1, timeout=OTP_REGISTER_TTL_SECONDS)
            messages.error(request, "Code has expired or is incorrect.")
            return render(request, 'registration/register.html', context)

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered. Please sign in.")
            return render(request, 'registration/register.html', context)

        try:
            validate_password(password)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return render(request, 'registration/register.html', context)

        User.objects.create_user(email=email, password=password, name=nickname)
        UserEmailOTP.objects.filter(
            email=email, purpose="register", used_at__isnull=True
        ).order_by("-created_at").update(used_at=timezone.now())
        cache.delete(otp_key)
        user = authenticate(request, username=email, password=password)
        if user is not None:
            auth_login(request, user)
            messages.success(request, "Welcome to Tango Finance.")
            return redirect('finance:transaction_list')
        messages.success(request, "Register success! Please sign in.")
        return redirect('login')
    return render(request, 'registration/register.html', context)

@require_POST
def send_code(request):
    email = (request.POST.get('email') or '').strip()
    if not email:
        return JsonResponse({'status': 'error', 'code': 'missing_email', 'message': 'Email required'}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'status': 'error', 'code': 'invalid_email', 'message': 'Invalid email address'}, status=400)

    cf_token = request.POST.get('cf_token', '')
    if not verify_turnstile(cf_token, request.META.get('REMOTE_ADDR')):
        return JsonResponse({'status': 'error', 'code': 'turnstile_failed', 'message': 'Security check failed. Please try again.'}, status=403)

    if User.objects.filter(email=email).exists():
        return JsonResponse({'status': 'error', 'code': 'email_taken', 'message': 'This email is already registered. Please sign in.'}, status=409)

    lock_key = f"otp_lock:reg:{email}"
    if cache.get(lock_key):
        return JsonResponse({'status': 'error', 'code': 'rate_limited', 'message': f'Wait {OTP_RATE_LIMIT_SECONDS}s.'}, status=429)

    code = secrets.randbelow(900000) + 100000
    code_hash = hashlib.sha256(str(code).encode("utf-8")).hexdigest()
    otp_record = UserEmailOTP.objects.create(
        email=email,
        code_hash=code_hash,
        purpose="register",
        expires_at=timezone.now() + timedelta(seconds=OTP_REGISTER_TTL_SECONDS),
        send_ip=request.META.get("REMOTE_ADDR"),
    )
    # Store hash in cache so plaintext OTP is never persisted outside memory.
    cache.set(f"finance:reg_otp:{email}", code_hash, timeout=OTP_REGISTER_TTL_SECONDS)
    cache.set(lock_key, True, timeout=OTP_RATE_LIMIT_SECONDS)
    try:
        _send_otp_email(
            recipient=email,
            code=code,
            purpose="register",
            ttl_seconds=OTP_REGISTER_TTL_SECONDS,
        )
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send registration OTP email")
        cache.delete(f"finance:reg_otp:{email}")
        cache.delete(lock_key)
        otp_record.delete()
        return JsonResponse(
            {'status': 'error', 'code': 'email_send_failed', 'message': 'Failed to send OTP email. Please retry.'},
            status=503,
        )
    return JsonResponse({'status': 'success'})

@login_required
def transaction_list(request):
    _ensure_starter_categories(request.user)
    base_items = Transaction.objects.filter(user=request.user).select_related("category")
    filters = _parse_transaction_filters(request)
    filtered_items = _apply_transaction_filters(base_items, filters, request)
    paginator = Paginator(filtered_items, TRANSACTION_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    items = page_obj.object_list

    today = date.today()
    month_qs = base_items.filter(occurred_at__year=today.year, occurred_at__month=today.month)
    month_income = month_qs.filter(type='Income').aggregate(Sum('amount_in_gbp'))['amount_in_gbp__sum'] or 0
    month_expense = month_qs.filter(type='Expense').aggregate(Sum('amount_in_gbp'))['amount_in_gbp__sum'] or 0
    month_net = month_income - month_expense

    expense_stats = month_qs.filter(type='Expense').values('category__name').annotate(total=Sum('amount_in_gbp'))
    chart_labels = [stat['category__name'] or 'General' for stat in expense_stats]
    chart_data = [float(stat['total']) for stat in expense_stats]

    behavior_insights = _build_behavior_insights(base_items)
    spending_summary, spending_summary_source = _build_spending_summary(
        request.user, base_items, behavior_insights
    )
    dashboard_visuals = _build_dashboard_visuals(base_items, month_income, month_expense)
    notifications = []
    if month_net < 0:
        notifications.append("Monthly net is negative. Consider reducing non-essential spending.")
    if behavior_insights["trend_direction"] == "up":
        notifications.append("Spending trend increased over the last 30 days.")
    if not notifications:
        notifications.append("No critical alerts. You're all caught up.")

    context = {
        'transactions': items,
        'categories': Category.objects.filter(user=request.user),
        'month_income': month_income,
        'month_expense': month_expense,
        'month_net': month_net,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'assistant_name': ASSISTANT_NAME,
        'query_text': filters["q"],
        'date_from': filters["date_from"],
        'date_to': filters["date_to"],
        'min_amount': filters["min_amount"],
        'max_amount': filters["max_amount"],
        'sort': filters["sort"],
        'result_count': paginator.count,
        'avg_daily_expense': behavior_insights["avg_daily_expense"],
        'top_category_name': behavior_insights["top_category_name"],
        'top_category_total': behavior_insights["top_category_total"],
        'largest_expense_amount': behavior_insights["largest_expense_amount"],
        'largest_expense_label': behavior_insights["largest_expense_label"],
        'trend_direction': behavior_insights["trend_direction"],
        'trend_percent': behavior_insights["trend_percent"],
        'spending_summary': spending_summary,
        'spending_summary_source': spending_summary_source,
        'expense_progress': dashboard_visuals["expense_progress"],
        'income_progress': dashboard_visuals["income_progress"],
        'focus_bar_heights': dashboard_visuals["focus_bar_heights"],
        'notifications': notifications,
        'site_search_items': get_site_search_items(),
        'page_obj': page_obj,
        'query_string_without_page': _build_query_without_page(request),
    }
    return render(request, 'finance/index.html', context)

@login_required
def add_transaction(request):
    if request.method == 'POST':
        try:
            cat_id = request.POST.get('category')
            category = get_object_or_404(Category, id=cat_id, user=request.user) if cat_id else None

            with transaction.atomic():
                create_transaction(
                    user=request.user,
                    category=category,
                    amount=request.POST.get('amount'),
                    currency=request.POST.get('currency', CURRENCY_CODES[0]),
                    occurred_at=request.POST.get('date') or timezone.now(),
                    note=request.POST.get('note', ''),
                    tx_type=request.POST.get('type'),
                )
                messages.success(request, "Record added.")
        except ValueError as exc:
            messages.error(request, str(exc))
            
    return redirect('finance:transaction_list')

@login_required
def edit_transaction(request, tid):
    item = Transaction.objects.filter(id=tid, user=request.user).first()
    if item is None:
        return HttpResponse(status=404)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                locked_item = Transaction.objects.select_for_update().get(id=tid, user=request.user)

                cat_id = request.POST.get('category')
                category = get_object_or_404(Category, id=cat_id, user=request.user) if cat_id else None

                update_transaction(
                    tx=locked_item,
                    amount=request.POST.get('amount'),
                    currency=request.POST.get('currency'),
                    tx_type=request.POST.get('type'),
                    note=request.POST.get('note', ''),
                    occurred_at=request.POST.get('date'),
                    category=category,
                )
                messages.success(request, "Updated successfully!")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('finance:transaction_list')
    
    return JsonResponse({
        'amount': str(item.original_amount),
        'currency': item.currency,
        'type': item.type,
        'date': item.occurred_at.strftime('%Y-%m-%dT%H:%M'),
        'note': item.note,
        'category': item.category.id if item.category else ''
    })

@login_required
@require_POST
def delete_transaction(request, tid):
    item = get_object_or_404(Transaction, id=tid, user=request.user)
    with transaction.atomic():
        item.delete()
    messages.success(request, "Record deleted.")
    return redirect('finance:transaction_list')

@login_required
def profile_view(request):
    currency_choices = list(CURRENCY_CODES)
    timezone_choices = list(PROFILE_TIMEZONE_CHOICES)

    if request.method == 'POST':
        new_name = request.POST.get('nickname')
        new_currency = request.POST.get("preferred_currency", CURRENCY_CODES[0])
        new_timezone = request.POST.get("preferred_timezone", PROFILE_TIMEZONE_CHOICES[0])

        if new_name:
            request.user.name = new_name[:50]
        if new_currency in currency_choices:
            request.user.preferred_currency = new_currency
        if new_timezone in timezone_choices:
            request.user.preferred_timezone = new_timezone
        request.user.save()
        messages.success(request, "Profile updated.")

    user_categories = Category.objects.filter(user=request.user)
    items = Transaction.objects.filter(user=request.user)
    today = date.today()
    month_qs = items.filter(occurred_at__year=today.year, occurred_at__month=today.month)

    month_totals = month_qs.aggregate(
        income=Sum('amount_in_gbp', filter=Q(type='Income')),
        expense=Sum('amount_in_gbp', filter=Q(type='Expense')),
    )
    month_income = month_totals['income'] or Decimal("0")
    month_expense = month_totals['expense'] or Decimal("0")
    month_net = month_income - month_expense

    bar_base = max(month_income, month_expense, Decimal("0.01"))
    income_bar = round(float(month_income / bar_base * 100), 1)
    expense_bar = round(float(month_expense / bar_base * 100), 1)
    net_bar = round(min(float(abs(month_net) / bar_base * 100), 100), 1)

    return render(request, 'finance/profile.html', {
        'user_categories': user_categories,
        'month_income': month_income,
        'month_expense': month_expense,
        'month_net': month_net,
        'income_bar': income_bar,
        'expense_bar': expense_bar,
        'net_bar': net_bar,
        'turnstile_site_key': CF_SITE_KEY,
        'turnstile_enabled': TURNSTILE_ENABLED,
        'currency_choices': currency_choices,
        'timezone_choices': timezone_choices,
    })

@login_required
@require_POST
def add_category(request):
    name = request.POST.get('cat_name', '').strip()
    if name:
        Category.objects.get_or_create(user=request.user, name=name, type_scope='Expense')
    return redirect('finance:profile')

@login_required
@require_POST
def delete_category(request, cat_id):
    category = get_object_or_404(Category, id=cat_id, user=request.user)
    # Keep transactions and clear category rather than deleting records.
    with transaction.atomic():
        Transaction.objects.filter(category=category).update(category=None)
        category.delete()
    return redirect('finance:profile')

@login_required
def send_delete_code(request):
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'code': 'method_not_allowed', 'message': 'POST required'}, status=405)

    lock_key = f"otp_lock:del:{request.user.id}"
    if cache.get(lock_key):
        return JsonResponse({'status': 'error', 'code': 'rate_limited', 'message': f'Wait {OTP_RATE_LIMIT_SECONDS}s.'}, status=429)
    
    code = str(secrets.randbelow(900000) + 100000)
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    otp_record = UserEmailOTP.objects.create(
        email=request.user.email,
        code_hash=code_hash,
        purpose="delete_account",
        expires_at=timezone.now() + timedelta(seconds=OTP_ACCOUNT_ACTION_TTL_SECONDS),
        send_ip=request.META.get("REMOTE_ADDR"),
    )
    cache.set(f"finance:del_otp:{request.user.id}", code_hash, timeout=OTP_ACCOUNT_ACTION_TTL_SECONDS)
    cache.set(lock_key, True, timeout=OTP_RATE_LIMIT_SECONDS)
    try:
        _send_otp_email(
            recipient=request.user.email,
            code=code,
            purpose="delete_account",
            ttl_seconds=OTP_ACCOUNT_ACTION_TTL_SECONDS,
        )
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send delete-account OTP email for user_id=%s", request.user.id)
        cache.delete(f"finance:del_otp:{request.user.id}")
        cache.delete(lock_key)
        otp_record.delete()
        return JsonResponse(
            {'status': 'error', 'code': 'email_send_failed', 'message': 'Failed to send OTP email. Please retry.'},
            status=503,
        )
    return JsonResponse({'status': 'success'})

@login_required
def delete_account(request):
    if request.method == 'POST':
        lock_id = f"lock:delete_user:{request.user.id}"
        # Prevent double-submit races on destructive account operations.
        lock_context = cache.lock(lock_id, timeout=10, blocking=False) if hasattr(cache, "lock") else nullcontext(True)
        with lock_context as acquired:
            if hasattr(cache, "lock") and not acquired:
                messages.warning(request, "Another delete request is in progress. Please retry shortly.")
                return redirect('finance:profile')
                
            input_code = request.POST.get('code')
            otp_key = f"finance:del_otp:{request.user.id}"
            stored_hash = cache.get(otp_key)
            input_hash = hashlib.sha256((input_code or "").encode("utf-8")).hexdigest()

            del_attempt_key = f"finance:del_otp_attempts:{request.user.id}"
            del_attempts = cache.get(del_attempt_key, 0)
            if del_attempts >= 5:
                messages.error(request, "Too many failed attempts. Please request a new code.")
                return redirect('finance:profile')

            if stored_hash and input_hash == stored_hash:
                with transaction.atomic():
                    UserEmailOTP.objects.filter(
                        email=request.user.email, purpose="delete_account", used_at__isnull=True
                    ).order_by("-created_at").update(used_at=timezone.now())
                    cache.delete(otp_key)
                    cache.delete(del_attempt_key)
                    request.user.delete()
                return redirect('login')
            else:
                cache.set(del_attempt_key, del_attempts + 1, timeout=OTP_ACCOUNT_ACTION_TTL_SECONDS)
                messages.error(request, "Invalid code.")
    return redirect('finance:profile')

@login_required
def send_pwd_code(request):
    if request.method != "POST":
        return JsonResponse({'status': 'error', 'code': 'method_not_allowed', 'message': 'POST required'}, status=405)

    lock_key = f"otp_lock:pwd:{request.user.id}"
    if cache.get(lock_key):
        return JsonResponse({'status': 'error', 'code': 'rate_limited', 'message': f'Wait {OTP_RATE_LIMIT_SECONDS}s.'}, status=429)
    
    code = str(secrets.randbelow(900000) + 100000)
    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    otp_record = UserEmailOTP.objects.create(
        email=request.user.email,
        code_hash=code_hash,
        purpose="change_password",
        expires_at=timezone.now() + timedelta(seconds=OTP_ACCOUNT_ACTION_TTL_SECONDS),
        send_ip=request.META.get("REMOTE_ADDR"),
    )
    cache.set(f"finance:pwd_otp:{request.user.id}", code_hash, timeout=OTP_ACCOUNT_ACTION_TTL_SECONDS)
    cache.set(lock_key, True, timeout=OTP_RATE_LIMIT_SECONDS)
    try:
        _send_otp_email(
            recipient=request.user.email,
            code=code,
            purpose="change_password",
            ttl_seconds=OTP_ACCOUNT_ACTION_TTL_SECONDS,
        )
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send password OTP email for user_id=%s", request.user.id)
        cache.delete(f"finance:pwd_otp:{request.user.id}")
        cache.delete(lock_key)
        otp_record.delete()
        return JsonResponse(
            {'status': 'error', 'code': 'email_send_failed', 'message': 'Failed to send OTP email. Please retry.'},
            status=503,
        )
    return JsonResponse({'status': 'success'})

@login_required
def change_password(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        new_password = request.POST.get('new_password')
        otp_key = f"finance:pwd_otp:{request.user.id}"
        stored_hash = cache.get(otp_key)
        input_hash = hashlib.sha256((code or "").encode("utf-8")).hexdigest()

        if stored_hash and input_hash == stored_hash:
            try:
                validate_password(new_password, request.user)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
                return redirect('finance:profile')

            with transaction.atomic():
                user = request.user
                user.set_password(new_password)
                user.save()
                UserEmailOTP.objects.filter(
                    email=user.email, purpose="change_password", used_at__isnull=True
                ).order_by("-created_at").update(used_at=timezone.now())
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                cache.delete(otp_key)
            messages.success(request, "Password changed!")
            return redirect('finance:profile')
        else:
            messages.error(request, "Invalid code.")
    return redirect('finance:profile')

@login_required
def export_csv(request):
    # Deterministic ordering helps users diff exports and avoids unstable file content.
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="tango_{date.today()}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Category', 'Amount', 'Currency', 'Amount(GBP)', 'Note'])
    for t in Transaction.objects.filter(user=request.user).select_related("category").order_by('-occurred_at'):
        writer.writerow([t.occurred_at, t.type, t.category.name if t.category else 'General',
                         t.original_amount, t.currency, t.amount_in_gbp, t.note])
    return response
