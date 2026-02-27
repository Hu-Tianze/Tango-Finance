from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone  
from django.core.cache import cache  
from django.db import transaction
from django.views.decorators.http import require_POST
import random
import csv
import requests  
from datetime import date, timedelta
import os

User = get_user_model()
from .models import Transaction, Category
from .services import create_transaction, update_transaction

CF_SECRET_KEY = os.getenv("CF_TURNSTILE_SECRET_KEY", "")

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
    except Exception as e:
        print(f"Cloudflare Error: {e}")
        return False

def register(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        nickname = request.POST.get('name') 
        password = request.POST.get('password')
        code_input = request.POST.get('code')
        
        otp_key = f"finance:reg_otp:{email}"
        real_code = cache.get(otp_key)
        
        if not real_code or code_input != str(real_code):
            messages.error(request, "Code has expired or is incorrect.")
            return render(request, 'registration/register.html')

        if User.objects.filter(email=email).exists():
            messages.info(request, "Email already registered.")
            return redirect('login')

        User.objects.create_user(email=email, password=password, name=nickname)
        cache.delete(otp_key)
        messages.success(request, "Register success!")
        return redirect('login')
    return render(request, 'registration/register.html')

def send_code(request):
    email = request.POST.get('email') or request.GET.get('email')
    cf_token = request.POST.get('cf_token') or request.GET.get('cf_token')
    if not email: return JsonResponse({'status': 'error', 'message': 'Email required'})
    if not verify_turnstile(cf_token, request.META.get('REMOTE_ADDR')):
        return JsonResponse({'status': 'error', 'message': 'Security check failed.'})
    
    lock_key = f"otp_lock:reg:{email}"
    if cache.get(lock_key): return JsonResponse({'status': 'error', 'message': 'Wait 60s.'})

    code = random.randint(100000, 999999)
    cache.set(f"finance:reg_otp:{email}", code, timeout=600)
    cache.set(lock_key, True, timeout=60)
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
    return render(request, 'finance/profile.html', {'user_categories': user_categories})

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
    return JsonResponse({'status': 'success'})

@login_required
def delete_account(request):
    if request.method == 'POST':
        lock_id = f"lock:delete_user:{request.user.id}"
        with cache.lock(lock_id, timeout=10, blocking=False) as acquired:
            if not acquired:
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
    return JsonResponse({'status': 'success'})

@login_required
def change_password(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        new_password = request.POST.get('new_password')
        otp_key = f"finance:pwd_otp:{request.user.id}"
        real_code = cache.get(otp_key)
        
        if real_code and code == str(real_code):
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
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="tango_{date.today()}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Category', 'Amount', 'Currency', 'Amount(GBP)', 'Note'])
    for t in Transaction.objects.filter(user=request.user).order_by('-occurred_at'):
        writer.writerow([t.occurred_at, t.type, t.category.name if t.category else 'General',
                         t.original_amount, t.currency, t.amount_in_gbp, t.note])
    return response
