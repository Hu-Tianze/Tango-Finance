from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone  
from django.core.cache import cache  
from django.db import transaction
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from contextlib import nullcontext
import logging
import random
import csv
import requests  
from datetime import date, timedelta
import os
import hashlib

User = get_user_model()
from .models import Transaction, Category
from .services import create_transaction, update_transaction
from user.models import EmailOTP as UserEmailOTP

CF_SECRET_KEY = os.getenv("CF_TURNSTILE_SECRET_KEY", "")
CF_SITE_KEY = os.getenv("CF_TURNSTILE_SITE_KEY", "0x4AAAAAACXuYkMEKTmY4upa")
logger = logging.getLogger(__name__)

def verify_turnstile(token, ip):
    if not token or not CF_SECRET_KEY:
        return False
    try:
        response = requests.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={'secret': CF_SECRET_KEY, 'response': token, 'remoteip': ip},
            timeout=5
        )
        return response.json().get('success', False)
    except requests.RequestException:
        logger.exception("Turnstile verification request failed")
        return False

def register(request):
    context = {"turnstile_site_key": CF_SITE_KEY}
    if request.method == 'POST':
        email = request.POST.get('email')
        nickname = request.POST.get('name') 
        password = request.POST.get('password')
        code_input = request.POST.get('code')
        
        otp_key = f"finance:reg_otp:{email}"
        real_code = cache.get(otp_key)
        
        if not real_code or code_input != str(real_code):
            messages.error(request, "Code has expired or is incorrect.")
            return render(request, 'registration/register.html', context)

        if User.objects.filter(email=email).exists():
            messages.info(request, "Email already registered.")
            return redirect('login')

        try:
            validate_password(password)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return render(request, 'registration/register.html', context)

        User.objects.create_user(email=email, password=password, name=nickname)
        cache.delete(otp_key)
        messages.success(request, "Register success!")
        return redirect('login')
    return render(request, 'registration/register.html', context)

@require_POST
def send_code(request):
    email = request.POST.get('email')
    cf_token = request.POST.get('cf_token')
    if not email: return JsonResponse({'status': 'error', 'message': 'Email required'})
    if not verify_turnstile(cf_token, request.META.get('REMOTE_ADDR')):
        return JsonResponse({'status': 'error', 'message': 'Security check failed.'})
    
    lock_key = f"otp_lock:reg:{email}"
    if cache.get(lock_key): return JsonResponse({'status': 'error', 'message': 'Wait 60s.'})

    code = random.randint(100000, 999999)
    # Store active OTP in cache for fast validation; store hashed copy in DB for audit traceability.
    cache.set(f"finance:reg_otp:{email}", code, timeout=600)
    cache.set(lock_key, True, timeout=60)
    UserEmailOTP.objects.create(
        email=email,
        code_hash=hashlib.sha256(str(code).encode("utf-8")).hexdigest(),
        purpose="register",
        expires_at=timezone.now() + timedelta(minutes=10),
        send_ip=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({'status': 'success'})

@login_required
def transaction_list(request):
    # Create starter categories for first-time users.
    if not Category.objects.filter(user=request.user).exists():
        for cat_name in ['Food', 'Transport', 'Housing', 'Shopping', 'Entertainment']:
            Category.objects.get_or_create(user=request.user, name=cat_name, type_scope='Expense')

    items = Transaction.objects.filter(user=request.user).order_by('-occurred_at')
    today = date.today()
    month_qs = items.filter(occurred_at__year=today.year, occurred_at__month=today.month)

    month_income = month_qs.filter(type='Income').aggregate(Sum('amount_in_gbp'))['amount_in_gbp__sum'] or 0
    month_expense = month_qs.filter(type='Expense').aggregate(Sum('amount_in_gbp'))['amount_in_gbp__sum'] or 0
    
    month_net = month_income - month_expense

    expense_stats = month_qs.filter(type='Expense').values('category__name').annotate(total=Sum('amount_in_gbp'))
    chart_labels = [stat['category__name'] or 'General' for stat in expense_stats]
    chart_data = [float(stat['total']) for stat in expense_stats]

    context = {
        'transactions': items,
        'categories': Category.objects.filter(user=request.user),
        'month_income': month_income,
        'month_expense': month_expense,
        'month_net': month_net,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
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
                    currency=request.POST.get('currency', 'GBP'),
                    occurred_at=request.POST.get('date') or timezone.now(),
                    note=request.POST.get('note', ''),
                    tx_type=request.POST.get('type'),
                )
                messages.success(request, "Record added.")
        except ValueError:
            messages.error(request, "Invalid amount format.")
        except Exception:
            logger.exception("Failed to add transaction for user_id=%s", request.user.id)
            messages.error(request, "Failed to add record.")
            
    return redirect('finance:transaction_list')

@login_required
def edit_transaction(request, tid):
    item = get_object_or_404(Transaction, id=tid, user=request.user)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                locked_item = Transaction.objects.select_for_update().get(id=tid)

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
        except ValueError:
            messages.error(request, "Update failed. Check your input.")
        except Exception:
            logger.exception("Failed to edit transaction id=%s for user_id=%s", tid, request.user.id)
            messages.error(request, "Update failed. Check your input.")
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
    if request.method == 'POST':
        new_name = request.POST.get('nickname')
        if new_name:
            request.user.name = new_name[:50]
            request.user.save()
            messages.success(request, "Nickname updated!")

    user_categories = Category.objects.filter(user=request.user)
    items = Transaction.objects.filter(user=request.user)
    today = date.today()
    month_qs = items.filter(occurred_at__year=today.year, occurred_at__month=today.month)

    month_income = month_qs.filter(type='Income').aggregate(Sum('amount_in_gbp'))['amount_in_gbp__sum'] or 0
    month_expense = month_qs.filter(type='Expense').aggregate(Sum('amount_in_gbp'))['amount_in_gbp__sum'] or 0
    month_net = month_income - month_expense

    return render(request, 'finance/profile.html', {
        'user_categories': user_categories,
        'month_income': month_income,
        'month_expense': month_expense,
        'month_net': month_net,
        'turnstile_site_key': CF_SITE_KEY,
    })

@login_required
def add_category(request):
    if request.method == 'POST':
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
    if request.method != "POST": return JsonResponse({'status': 'error'})
    cf_token = request.POST.get('cf_token')
    if not verify_turnstile(cf_token, request.META.get('REMOTE_ADDR')):
        return JsonResponse({'status': 'error', 'message': 'Security check failed.'})

    lock_key = f"otp_lock:del:{request.user.id}"
    if cache.get(lock_key): return JsonResponse({'status': 'error', 'message': 'Wait 60s.'})
    
    code = f"{random.randint(100000, 999999)}"
    cache.set(f"finance:del_otp:{request.user.id}", code, timeout=300)
    cache.set(lock_key, True, timeout=60)
    UserEmailOTP.objects.create(
        email=request.user.email,
        code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
        purpose="delete_account",
        expires_at=timezone.now() + timedelta(minutes=5),
        send_ip=request.META.get("REMOTE_ADDR"),
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
                return JsonResponse({'status': 'error', 'message': 'Processing...'})
                
            input_code = request.POST.get('code')
            otp_key = f"finance:del_otp:{request.user.id}"
            real_code = cache.get(otp_key)
            
            if real_code and input_code == str(real_code):
                with transaction.atomic():
                    cache.delete(otp_key)
                    request.user.delete()
                return redirect('login')
            else:
                messages.error(request, "Invalid code.")
    return redirect('finance:profile')

@login_required
def send_pwd_code(request):
    if request.method != "POST": return JsonResponse({'status': 'error'})
    cf_token = request.POST.get('cf_token')
    if not verify_turnstile(cf_token, request.META.get('REMOTE_ADDR')):
        return JsonResponse({'status': 'error', 'message': 'Security check failed.'})

    lock_key = f"otp_lock:pwd:{request.user.id}"
    if cache.get(lock_key): return JsonResponse({'status': 'error', 'message': 'Wait 60s.'})
    
    code = f"{random.randint(100000, 999999)}"
    cache.set(f"finance:pwd_otp:{request.user.id}", code, timeout=300)
    cache.set(lock_key, True, timeout=60)
    UserEmailOTP.objects.create(
        email=request.user.email,
        code_hash=hashlib.sha256(code.encode("utf-8")).hexdigest(),
        purpose="change_password",
        expires_at=timezone.now() + timedelta(minutes=5),
        send_ip=request.META.get("REMOTE_ADDR"),
    )
    return JsonResponse({'status': 'success'})

@login_required
def change_password(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        new_password = request.POST.get('new_password')
        otp_key = f"finance:pwd_otp:{request.user.id}"
        real_code = cache.get(otp_key)
        
        if real_code and code == str(real_code):
            try:
                validate_password(new_password, request.user)
            except ValidationError as exc:
                messages.error(request, " ".join(exc.messages))
                return redirect('finance:profile')

            with transaction.atomic():
                user = request.user
                user.set_password(new_password)
                user.save()
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
    for t in Transaction.objects.filter(user=request.user).order_by('-occurred_at'):
        writer.writerow([t.occurred_at, t.type, t.category.name if t.category else 'General',
                         t.original_amount, t.currency, t.amount_in_gbp, t.note])
    return response
