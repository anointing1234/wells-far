from django.shortcuts import render,get_object_or_404, redirect
from django.contrib.auth.models import User
from decimal import Decimal, InvalidOperation
from django.core.mail import EmailMessage
from django.utils.html import strip_tags
from django.contrib.auth import login,authenticate
from django.contrib import messages
from django.urls import reverse
from django.db import IntegrityError
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth import logout as auth_logout,login as auth_login,authenticate
from django.contrib.auth.decorators import login_required
from django.db.models.signals import post_save
from django.http import JsonResponse
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.hashers import check_password
from django.views.decorators.csrf import csrf_protect
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password,check_password
from django.utils.decorators import method_decorator
from django.core.mail import send_mail
import os
from email.mime.image import MIMEImage
from django.conf import settings
import shutil
from requests.exceptions import ConnectionError
import requests 
import uuid
import re
# from accounts.form import SignupForm,LoginForm,TransferForm,LoanRequestForm,CardForm,SendresetcodeForm,ProfileEditForm 
from .models import (
Transaction,Deposit,TransferCode, 
Transfer, Beneficiary,AccountBalance,
PaymentGateway,
LoanRequest)
import random
from .models import Account
from django.utils.crypto import get_random_string
from django.utils.timezone import now, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.admin import AdminSite
from django.utils.translation import gettext_lazy as _
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
import logging
from django.db import transaction
from django.db.models import Sum,Avg
from django.db.models.functions import TruncDate
from django.db.models.functions import TruncDate, TruncWeek
from django.utils.timezone import now
import calendar
from django.core.exceptions import ValidationError
from django.contrib.auth import update_session_auth_hash
from email import message_from_bytes
logger = logging.getLogger(__name__)
import threading
import resend


# home views pages

def home(request):
    return render(request,'home/index.html')


def about_us(request):
    return render(request,'home/about.html')


def services(request):
    return render(request,'home/services.html')


def ppp_trading(request):
    return render(request,'home/PPP_Trading.html')


def contact(request):
    return render(request,'home/contact.html')


def faq(request):
    return render(request,'home/faq.html')









def login_view(request):
    # form = LoginForm()
    return render(request, 'Dashboard/forms/login.html',
                #   {'form':form}
                  )  

def signup_view(request):
    # form = SignupForm()   
    return render(request, 'Dashboard/forms/signup.html',
                #   {'form':form}
                  )



@login_required
def dashboard(request):
    # Recent 10 transactions
    transactions = Transaction.objects.filter(user=request.user).order_by('-transaction_date')[:10]

    # Get the latest loan request for this user (optional: you can also fetch all)
    loan = LoanRequest.objects.filter(user=request.user).order_by('-date').first()

    # Get current month start and end
    today = now().date()
    month_start = today.replace(day=1)
    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = today.replace(day=last_day)

    # Total transaction amount for this month
    total_amount = (
        Transaction.objects.filter(user=request.user, transaction_date__date__range=(month_start, month_end))
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    # Daily totals (for avg per day)
    daily_totals = (
        Transaction.objects.filter(user=request.user, transaction_date__date__range=(month_start, month_end))
        .annotate(date_only=TruncDate('transaction_date'))
        .values('date_only')
        .annotate(total_amount=Sum('amount'))
        .order_by('date_only')
    )

    per_day_avg = 0
    if daily_totals:
        per_day_avg = sum(d['total_amount'] for d in daily_totals) / len(daily_totals)

    # Weekly totals
    week_totals = []
    chart_labels = []

    current = month_start
    week_num = 1
    while current <= month_end:
        week_start = current
        week_end = min(current + timedelta(days=6), month_end)

        total = (
            Transaction.objects.filter(
                user=request.user,
                transaction_date__date__range=(week_start, week_end)
            ).aggregate(total=Sum('amount'))['total'] or 0
        )

        week_totals.append(total)
        chart_labels.append(f"Week {week_num}")

        current = week_end + timedelta(days=1)
        week_num += 1

    context = {
        'transactions': transactions,
        'total_amount': total_amount,
        'per_day_avg': per_day_avg,
        'chart_data': week_totals,
        'chart_labels': chart_labels,
        'loan': loan,  # This will be None if the user has no loans
    }
    return render(request, 'Dashboard/index.html', context)


@login_required
def deposit_view(request):
    deposits = Deposit.objects.filter(user=request.user).order_by('-date')
    return render(request,'Dashboard/fianaces/deposit.html',{'deposits':deposits})

@login_required
def local_transfer_view(request):
    beneficiaries = Beneficiary.objects.filter(user=request.user)
    context = {
          'beneficiaries': beneficiaries,
    }
    return render(request,'Dashboard/fianaces/local_transfer.html',context)    


@login_required
def international_transfer_view(request):
    beneficiaries = Beneficiary.objects.filter(user=request.user)
    context = {
          'beneficiaries': beneficiaries,
    }
    return render(request,'Dashboard/fianaces/international_transfer.html',context)



@login_required
def loans_views(request):
    return render(request,'Dashboard/fianaces/loans.html',)


@login_required
def grants(request):
    loans = LoanRequest.objects.filter(user=request.user).order_by('-date')
    return render(request,'Dashboard/fianaces/grants.html',{'loans': loans})


@login_required
def profile_view(request):
    return render(request,'Dashboard/profile.html')



@login_required
def bank_statement(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-transaction_date')

    context = {
        'transactions': transactions,
    }
    return render(request,'Dashboard/fianaces/bank_statements.html',context)

def async_send_resend_email(to_email=None, subject=None, html_body=None, msg=None, from_email="Nibc <info@bnunited.com>"):
    """
    Send an email via Resend asynchronously.
    - If `msg` is provided (EmailMultiAlternatives), extract HTML content and use its recipient and subject.
    - If `to_email`, `subject`, and `html_body` are provided, use them directly.
    - `from_email` defaults to a verified sender but can be overridden by `msg.from_email`.
    """
    resend.api_key = os.getenv("RESEND_API_KEY")
    if not resend.api_key:
        logger.error("RESEND_API_KEY is not set")
        return

    def clean_email(email):
        """Extract a plain email address from a string like 'Name <email@example.com>' or 'email@example.com'."""
        if not email:
            logger.error("No email address provided for 'from' field")
            return None
        # Match email address in the format 'Name <email@example.com>' or 'email@example.com'
        match = re.match(r'^(?:.*?<)?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>?$', email)
        if match:
            return match.group(1)
        logger.error(f"Invalid email format: {email}")
        return None

    def send_email():
        try:
            if msg:
                # Extract HTML from EmailMultiAlternatives
                raw_msg = msg.message().as_bytes()
                parsed_msg = message_from_bytes(raw_msg)
                html_content = ""
                for part in parsed_msg.walk():
                    if part.get_content_type() == "text/html":
                        html_content = part.get_payload(decode=True).decode()
                        break
                if not html_content:
                    logger.warning("No HTML content found in email, using plain text as fallback")
                    html_content = msg.body or "No content available"
                
                # Clean and validate from_email
                cleaned_from_email = clean_email(msg.from_email)
                if not cleaned_from_email:
                    logger.error(f"Invalid from_email in msg: {msg.from_email}")
                    return
                
                email_params = {
                    "from": f"Nibc <{cleaned_from_email}>",
                    "to": msg.to,
                    "subject": msg.subject,
                    "html": html_content
                }
            else:
                # Use direct parameters
                if not (to_email and subject and html_body):
                    logger.error("Missing required email parameters")
                    return
                
                # Clean and validate from_email
                cleaned_from_email = clean_email(from_email)
                if not cleaned_from_email:
                    logger.error(f"Invalid from_email: {from_email}")
                    return
                
                email_params = {
                    "from": f"Nibc <{cleaned_from_email}>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body
                }

            # Log the email_params for debugging
            logger.debug(f"Sending email with params: {email_params}")

            # Send email via Resend
            response = resend.Emails.send(email_params)
            logger.info(f"Email sent successfully to {email_params['to']}: {response}")

        except Exception as e:
            logger.error(f"Resend email failed for {email_params.get('to', 'unknown')}: {str(e)}")

    threading.Thread(target=send_email, daemon=True).start()


def async_send_resend_email(to_email=None, subject=None, html_body=None, msg=None, from_email="Nibc <info@bnunited.com>"):
    """
    Send an email via Resend asynchronously.
    - If `msg` is provided (EmailMultiAlternatives), extract HTML content and use its recipient and subject.
    - If `to_email`, `subject`, and `html_body` are provided, use them directly.
    - `from_email` defaults to a verified sender but can be overridden by `msg.from_email`.
    """
    resend.api_key = os.getenv("RESEND_API_KEY")
    if not resend.api_key:
        logger.error("RESEND_API_KEY is not set")
        return

    def send_email():
        try:
            if msg:
                # Extract HTML from EmailMultiAlternatives
                raw_msg = msg.message().as_bytes()
                html_content = ""
                parsed_msg = message_from_bytes(raw_msg)
                for part in parsed_msg.walk():
                    if part.get_content_type() == "text/html":
                        html_content = part.get_payload(decode=True).decode()
                        break
                if not html_content:
                    logger.warning("No HTML content found in email, using plain text as fallback")
                    html_content = msg.body or "No content available"
                email_params = {
                    "from": f"Nibc <{msg.from_email}>",
                    "to": msg.to,
                    "subject": msg.subject,
                    "html": html_content
                }
            else:
                # Use direct parameters
                if not (to_email and subject and html_body):
                    logger.error("Missing required email parameters")
                    return
                email_params = {
                    "from": from_email,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body
                }

            # Send email via Resend
            response = resend.Emails.send(email_params)
            logger.info(f"Email sent successfully to {email_params['to']}: {response}")

        except Exception as e:
            logger.error(f"Resend email failed for {email_params.get('to', 'unknown')}: {str(e)}")

    threading.Thread(target=send_email, daemon=True).start()



def register(request):
    if request.method == 'POST':
        # Extract POST data
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone_number = request.POST.get('phone_number', '')
        country = request.POST.get('country', '')
        city = request.POST.get('city', '')
        gender = request.POST.get('gender', '')
        account_type = request.POST.get('account_type', 'savings')

        # Validation
        errors = []
        if not email:
            errors.append("Email is required.")
        elif Account.objects.filter(email=email).exists():
            errors.append("Email is already registered.")
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if gender and gender not in ['M', 'F', 'O']:
            errors.append("Invalid gender selection.")
        if account_type not in ['savings', 'current', 'fixed', 'offshore']:
            errors.append("Invalid account type.")

        if errors:
            return JsonResponse({'success': False, 'message': " ".join(errors)})

        try:
            # Create the user (password=None since PINs will be used for login)
            user = Account.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                country=country,
                city=city,
                gender=gender,
                account_type=account_type
            )

            # Generate fresh raw PINs and hash them
            plain_login_pin = user.generate_random_number(6)
            plain_transaction_pin = user.generate_random_number(4)
            user.login_pin = make_password(plain_login_pin)
            user.transaction_pin = make_password(plain_transaction_pin)

            # Unique username (short prefix + random 4 digits)
            base_username = user.email.split('@')[0][:5]
            user.username = f"{base_username}{str(uuid.uuid4().int)[:4]}"

            user.save()

            # Prepare Email
            email_subject = 'Welcome to Nibc Online Bank'
            email_body = f"""
            <html>
            <head>
              <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 8px; }}
                .logo {{ text-align: center; margin-bottom: 20px; }}
                .btn {{ display: inline-block; padding: 10px 20px; background-color: #007bff; color: #fff; text-decoration: none; border-radius: 5px; }}
              </style>
            </head>
            <body>
              <div class="container">
                <div class="logo">
                  <img src="{request.build_absolute_uri('/static/assets/images/logo-dark.png')}" alt="Nibc Logo" width="120">
                </div>
                <h2>Welcome, {user.first_name} {user.last_name}!</h2>
                <p>Your account has been successfully created at <strong>Nibc </strong>.</p>
                <p><strong>Login PIN:</strong> {plain_login_pin}<br>
                   <strong>Transaction PIN:</strong> {plain_transaction_pin}</p>
                <p>Please keep these PINs secure.</p>
                <p>Thank you for joining us!</p>
                <p>&copy; {timezone.now().year} Nibc </p>
              </div>
            </body>
            </html>
            """

            # Send email asynchronously using Resend
            async_send_resend_email(to_email=user.email, subject=email_subject, html_body=email_body)

            return JsonResponse({
                'success': True,
                'message': 'Account created! A welcome email has been sent with your login and transaction PINs.',
                'redirect_url': reverse('login')
            })

        except Exception as e:
            logger.exception(f"Registration failed for email {email}: {str(e)}")
            return JsonResponse({'success': False, 'message': 'An error occurred. Please try again.'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'})




def login_Account(request):
    if request.method == 'POST':
        # Extract POST data
        account_id = request.POST.get('account_id','').strip()   # Can be Account ID or Email
        login_pin = request.POST.get('login_pin','').strip() 

        # 🔎 Debug prints
        print("🔎 Raw POST Data:", request.POST)
        print("➡️ account_id received:", account_id)
        print("➡️ login_pin received:", login_pin)

        # Validate required fields
        errors = []
        if not account_id:
            errors.append("Account ID or Email is required.")
        if not login_pin:
            errors.append("Login PIN is required.")
        elif len(login_pin) != 6 or not login_pin.isdigit():
            errors.append("Login PIN must be exactly 6 digits.")

        if errors:
            error_message = "\n".join(errors)
            print("❌ Validation errors:", error_message)  # Debug
            return JsonResponse({
                'success': False,
                'message': error_message
            })

        dashboard_url = reverse('dashboard')

        # Authenticate the user using custom PinBackend
        user = authenticate(request, account_id=account_id, login_pin=login_pin)

        # 🔎 Debug what authenticate returns
        print("✅ Authenticated User:", user)

        if user is not None:
            # Check account status before allowing login
            print("📌 User Status:", user.status)
            if user.status in ['active', 'inactive']:
                auth_login(request, user)
                return JsonResponse({
                    'success': True,
                    'message': 'Login successful!',
                    'redirect_url': dashboard_url
                })
            else:
                print("❌ Blocked/Disabled Account:", user.email)
                return JsonResponse({
                    'success': False,
                    'message': 'Your account has been blocked or disabled. '
                               'Please contact admin at '
                               '<a href="mailto:info@globaltrustbc.com">info@globaltrustbc.com</a> for assistance.'
                })
        else:
            print("❌ Authentication failed for:", account_id, login_pin)
            return JsonResponse({
                'success': False,
                'message': 'Invalid Account ID/Email or Login PIN. Please try again.'
            })

    else:
        return render(request, 'forms/login.html')



def logout_view(request):
    auth_logout(request)
    # form = LoginForm()
    return render(
    request,'Dashboard/forms/login.html',
    # {'form':form}
    )






def transaction_receipt_view(request, reference):
       transaction = get_object_or_404(Transfer, reference=reference)
       beneficiary = transaction.beneficiary

       # Prepare context for the template
       context = {
           "sender_name": f"{transaction.user.first_name} {transaction.user.last_name}",
           "sender_account_number": getattr(transaction.user, "account_number", "N/A"),
           "sender_account_type": "checking" ,
           "receiver_name": beneficiary.full_name,
           "receiver_account_number": beneficiary.account_number,
           "receiver_bank": beneficiary.bank_name,
           "receiver_bank_address": beneficiary.bank_address,
           "transaction_reference": transaction.reference,
           "transaction_date": transaction.date.strftime("%Y-%m-%d %H:%M:%S"),
           "amount": transaction.amount,
           "region": transaction.region,
       }
       return render(request, "Dashboard/emails/receipt_template.html", context)
   



@login_required
def validate_pin(request):
    if request.method == 'POST':
        pin = request.POST.get('pin', '').strip()
        user = request.user

        # Debug logs
        print("----- PIN VALIDATION DEBUG -----")
        print(f"User inputed pin: {pin}")
        print(f"User raw_transaction_pin (from DB): {user.raw_transaction_pin}")
        print("--------------------------------")

        # Direct comparison with raw_transaction_pin
        if pin == str(user.raw_transaction_pin):
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'message': 'Invalid PIN'}, status=400)

    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)

@login_required
def send_transfer_code(request):
    if request.method == 'POST':
        try:
            # Log request data for debugging
            logger.info(f"Processing send_transfer_code for user: {request.user}")

            # Delete any previous unused/unexpired codes
            TransferCode.objects.filter(user=request.user, used=False).delete()

            # Generate unique codes
            def generate_unique_code(field):
                code = get_random_string(length=6, allowed_chars='0123456789')
                while TransferCode.objects.filter(**{field: code}).exists():
                    code = get_random_string(length=6, allowed_chars='0123456789')
                return code

            transfer_code = TransferCode.objects.create(
                user=request.user,
                tac_code=generate_unique_code('tac_code'),
                tax_code=generate_unique_code('tax_code'),
                atc_code=generate_unique_code('atc_code'),
                freeze_code=generate_unique_code('freeze_code'),
                expires_at=timezone.now() + timedelta(hours=1)
            )

            return JsonResponse({
                'success': True,
                'message': 'New transfer codes generated successfully',
                'codes': {
                    'tac_code': transfer_code.tac_code,
                    'tax_code': transfer_code.tax_code,
                    'atc_code': transfer_code.atc_code,
                    'freeze_code': transfer_code.freeze_code,
                    'expires_at': transfer_code.expires_at.isoformat()
                }
            })
        except Exception as e:
            logger.error(f"Error in send_transfer_code: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Internal server error: {str(e)}'
            }, status=500)
    return JsonResponse({
        'success': False,
        'message': 'Invalid request'
    }, status=400)


@login_required
def validate_code(request):
    if request.method == 'POST':
        # Normalize inputs
        code = request.POST.get('code', '').strip().replace(" ", "")
        code_type = request.POST.get('code_type', '').strip()

        transfer_code = TransferCode.objects.filter(
            user=request.user,
            used=False,
            expires_at__gt=timezone.now()
        ).first()

        if not transfer_code:
            return JsonResponse({'success': False, 'message': 'No valid transfer codes found'}, status=400)

        # Compare after normalization
        if code_type == 'tac_code' and code == transfer_code.tac_code:
            return JsonResponse({'success': True})
        if code_type == 'tax_code' and code == transfer_code.tax_code:
            return JsonResponse({'success': True})
        if code_type == 'atc_code' and code == transfer_code.atc_code:
            return JsonResponse({'success': True})
        if code_type == 'freeze_code' and code == transfer_code.freeze_code:
            return JsonResponse({'success': True, 'message': 'Freeze code validated'})

        return JsonResponse({'success': False, 'message': f'Invalid {code_type}'}, status=400)

    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=400)


def local_transfer_views(request):
    if request.method == 'POST':
        try:
            # Extract and validate form data
            from_account = request.POST.get('from_account')
            raw_amount = request.POST.get('amount')
            beneficiary_id = request.POST.get('beneficiary')
            account_holder = request.POST.get('account_holder')
            to_account = request.POST.get('to_account')
            bank_name = request.POST.get('bank_name')
            routing_number = request.POST.get('routing_number')
            swift_code = request.POST.get('swift_code')
            description = request.POST.get('description') or "Local transfer"
            transaction_pin = request.POST.get('transaction_pin','').strip() 
            currency = request.POST.get('currency', 'USD').upper()
            bank_address = request.POST.get('bank_address')

            # Validate required fields
            if not from_account or from_account not in ['checking', 'loan']:
                return JsonResponse({'success': False, 'message': 'Invalid or missing account type'}, status=400)
            if not to_account or not bank_name:
                return JsonResponse({'success': False, 'message': 'Recipient account number and bank name are required'}, status=400)
            if not transaction_pin:
                return JsonResponse({'success': False, 'message': 'Transaction PIN is required'}, status=400)
            try:
                amount = Decimal(raw_amount)
                if amount <= 0:
                    return JsonResponse({'success': False, 'message': 'Amount must be greater than zero'}, status=400)
            except (TypeError, ValueError, InvalidOperation):
                return JsonResponse({'success': False, 'message': 'Invalid amount'}, status=400)

            user = request.user

            # Verify PIN
            if hasattr(user, "pin") and not check_password(transaction_pin, user.pin):
                return JsonResponse({'success': False, 'message': 'Invalid transaction PIN'}, status=400)

            # Get and validate account balance
            try:
                balance = AccountBalance.objects.get(account=user)
            except AccountBalance.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Account balance not found'}, status=400)

            # Balance check
            if currency == 'USD':
                if from_account == 'checking':
                    current_balance = balance.checking_balance
                elif from_account == 'loan':
                    current_balance = balance.loan_balance
                else:
                    return JsonResponse({'success': False, 'message': 'Invalid account type'}, status=400)
            elif currency == 'GBP':
                current_balance = balance.gbp
            elif currency == 'EUR':
                current_balance = balance.eur
            else:
                return JsonResponse({'success': False, 'message': 'Unsupported currency'}, status=400)

            if amount > current_balance:
                return JsonResponse({'success': False, 'message': 'Insufficient balance'}, status=400)

            # Atomic transaction
            with transaction.atomic():
                # Deduct balance
                if currency == 'USD':
                    if from_account == 'checking':
                        balance.checking_balance -= amount
                        balance.available_balance -= amount
                        remaining_balance = balance.checking_balance
                    elif from_account == 'loan':
                        balance.loan_balance -= amount
                        remaining_balance = balance.loan_balance
                elif currency == 'GBP':
                    balance.gbp -= amount
                    remaining_balance = balance.gbp
                elif currency == 'EUR':
                    balance.eur -= amount
                    remaining_balance = balance.eur
                balance.save()

                # Beneficiary handling
                if beneficiary_id:
                    try:
                        beneficiary = Beneficiary.objects.get(id=beneficiary_id, user=user)
                    except Beneficiary.DoesNotExist:
                        return JsonResponse({'success': False, 'message': 'Invalid beneficiary'}, status=400)
                else:
                    if not account_holder:
                        return JsonResponse({'success': False, 'message': 'Beneficiary account holder name is required'}, status=400)
                    beneficiary, _ = Beneficiary.objects.get_or_create(
                        user=user,
                        full_name=account_holder,
                        account_number=to_account,
                        bank_name=bank_name,
                        routing_transit_number=routing_number or "",
                        swift_code=swift_code or "",
                        bank_address=bank_address or "N/A"
                    )

                # Unique transaction reference
                unique_reference = str(uuid.uuid4())

                # Transaction record
                transaction_record = Transaction.objects.create(
                    user=user,
                    amount=amount,
                    transaction_type='transfer',
                    description=description,
                    status='pending',
                    reference=unique_reference,
                    institution=bank_name,
                    to_account=to_account,
                    from_account=getattr(user, 'account_number', 'N/A')
                )

                # Transfer record
                Transfer.objects.create(
                    user=user,
                    beneficiary=beneficiary,
                    amount=amount,
                    reason=description,
                    status='pending',
                    remarks='Local transfer completed',
                    charge=Decimal("0.00"),
                    region='local',
                    reference=unique_reference
                )

            debit_context = {
                "sender_name": f"{user.first_name} {user.last_name}",
                "sender_account_number": getattr(user, "account_number", "N/A"),
                "sender_account_type": from_account,
                "receiver_name": beneficiary.full_name,
                "receiver_account_number": beneficiary.account_number,
                "receiver_bank": beneficiary.bank_name,
                "receiver_bank_address": beneficiary.bank_address,
                "transaction_reference": unique_reference,
                "transaction_date": timezone.localtime(transaction_record.transaction_date).strftime("%Y-%m-%d %H:%M:%S"),
                "region": "local",
            }

            # Send Debit Notification Email via Resend
            try:
                email_subject = "Nibc Debit Notification"
                email_body = render_to_string("Dashboard/emails/receipt_template.html", debit_context)

                if not user.email or '@' not in user.email:
                    logger.warning(f"Invalid or missing email for user {user.id}")
                else:
                    msg = EmailMultiAlternatives(
                        email_subject,
                        "",
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                    )
                    msg.mixed_subtype = "related"
                    msg.attach_alternative(email_body, "text/html")

                    # Attach logo if exists
                    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
                    if os.path.exists(logo_path):
                        from email.mime.image import MIMEImage
                        with open(logo_path, 'rb') as f:
                            img = MIMEImage(f.read())
                            img.add_header('Content-ID', '<logo.png>')
                            img.add_header('Content-Disposition', 'inline', filename='logo.png')
                            msg.attach(img)
                    else:
                        logger.warning(f"Logo file not found at {logo_path}")

                    async_send_resend_email(msg=msg)
                    logger.info(f"Debit notification email sent to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send email to {user.email}: {str(e)}")

            # Return JSON with receipt URL
            receipt_url = reverse("transaction_receipt", args=[unique_reference])
            return JsonResponse({
                "success": True,
                "message": "Transfer successful.",
                "redirect_url": receipt_url
            })

        except Exception as e:
            logger.error(f"Transfer failed for user {request.user.email}: {str(e)}")
            return JsonResponse({'success': False, 'message': f'Transfer failed: {str(e)}'}, status=500)

    else:
        context = {
            'beneficiaries': Beneficiary.objects.filter(user=request.user),
        }
        return render(request, 'dashboard/finances/local_transfer.html', context)

def Transfer_views(request):
    if request.method == 'POST':
        try:
            # Extract and validate form data
            from_account = request.POST.get('from_account')
            raw_amount = request.POST.get('amount')
            beneficiary_id = request.POST.get('beneficiary')
            account_holder = request.POST.get('account_holder')
            to_account = request.POST.get('to_account')
            bank_name = request.POST.get('bank_name')
            routing_number = request.POST.get('routing_number')
            swift_code = request.POST.get('swift_code')
            description = request.POST.get('description') or "International transfer"
            transaction_pin = request.POST.get('transaction_pin','').strip() 
            currency = request.POST.get('currency', 'USD').upper()
            bank_address = request.POST.get('bank_address')

            # Validate required fields
            if not from_account or from_account not in ['checking', 'loan']:
                return JsonResponse({'success': False, 'message': 'Invalid or missing account type'}, status=400)
            if not to_account:
                return JsonResponse({'success': False, 'message': 'Recipient account number is required'}, status=400)
            if not bank_name:
                return JsonResponse({'success': False, 'message': 'Bank name is required'}, status=400)
            if not transaction_pin:
                return JsonResponse({'success': False, 'message': 'Transaction PIN is required'}, status=400)
            try:
                amount = Decimal(raw_amount)
                if amount <= 0:
                    return JsonResponse({'success': False, 'message': 'Amount must be greater than zero'}, status=400)
            except (TypeError, ValueError, InvalidOperation):
                return JsonResponse({'success': False, 'message': 'Invalid amount'}, status=400)

            user = request.user

            # Verify PIN
            if hasattr(user, "pin") and not check_password(transaction_pin, user.pin):
                return JsonResponse({'success': False, 'message': 'Invalid transaction PIN'}, status=400)

            # Get and validate account balance
            try:
                balance = AccountBalance.objects.get(account=user)
            except AccountBalance.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Account balance not found'}, status=400)

            # Balance check
            if currency == 'USD':
                if from_account == 'checking':
                    current_balance = balance.checking_balance
                elif from_account == 'loan':
                    current_balance = balance.loan_balance
                else:
                    return JsonResponse({'success': False, 'message': 'Invalid account type'}, status=400)
            elif currency == 'GBP':
                current_balance = balance.gbp
            elif currency == 'EUR':
                current_balance = balance.eur
            else:
                return JsonResponse({'success': False, 'message': 'Unsupported currency'}, status=400)

            if amount > current_balance:
                return JsonResponse({'success': False, 'message': 'Insufficient balance'}, status=400)

            # Atomic transaction
            with transaction.atomic():
                # Deduct balance
                if currency == 'USD':
                    if from_account == 'checking':
                        balance.checking_balance -= amount
                        balance.available_balance -= amount
                        remaining_balance = balance.checking_balance
                    elif from_account == 'loan':
                        balance.loan_balance -= amount
                        remaining_balance = balance.loan_balance
                elif currency == 'GBP':
                    balance.gbp -= amount
                    remaining_balance = balance.gbp
                elif currency == 'EUR':
                    balance.eur -= amount
                    remaining_balance = balance.eur
                balance.save()

                # Beneficiary handling
                if beneficiary_id:
                    try:
                        beneficiary = Beneficiary.objects.get(id=beneficiary_id, user=user)
                    except Beneficiary.DoesNotExist:
                        return JsonResponse({'success': False, 'message': 'Invalid beneficiary'}, status=400)
                else:
                    if not account_holder:
                        return JsonResponse({'success': False, 'message': 'Beneficiary account holder name is required'}, status=400)
                    beneficiary, _ = Beneficiary.objects.get_or_create(
                        user=user,
                        full_name=account_holder,
                        account_number=to_account,
                        bank_name=bank_name,
                        routing_transit_number=routing_number or "",
                        swift_code=swift_code or "",
                        bank_address=bank_address or "N/A"
                    )

                # Unique transaction reference
                unique_reference = str(uuid.uuid4())

                # Transaction record
                transaction_record = Transaction.objects.create(
                    user=user,
                    amount=amount,
                    transaction_type='transfer',
                    description=description,
                    status='pending',
                    reference=unique_reference,
                    institution=bank_name,
                    to_account=to_account,
                    from_account=getattr(user, 'account_number', 'N/A')
                )

                # Transfer record
                Transfer.objects.create(
                    user=user,
                    beneficiary=beneficiary,
                    amount=amount,
                    reason=description,
                    status='pending',
                    remarks='International transfer completed',
                    charge=Decimal("0.00"),
                    region='international',
                    reference=unique_reference
                )

            # Prepare context for template & email
            debit_context = {
                "sender_name": f"{user.first_name} {user.last_name}",
                "sender_account_number": getattr(user, "account_number", "N/A"),
                "sender_account_type": from_account,
                "receiver_name": beneficiary.full_name,
                "receiver_account_number": beneficiary.account_number,
                "receiver_bank": beneficiary.bank_name,
                "receiver_bank_address": beneficiary.bank_address,
                "transaction_reference": unique_reference,
                "transaction_date": timezone.localtime(transaction_record.transaction_date).strftime("%Y-%m-%d %H:%M:%S"),
                "region": "international",
            }

            # Send Debit Notification Email via Resend
            try:
                email_subject = "Nibc Debit Notification"
                email_body = render_to_string("Dashboard/emails/receipt_template.html", debit_context)

                if not user.email or '@' not in user.email:
                    logger.warning(f"Invalid or missing email for user {user.id}")
                else:
                    msg = EmailMultiAlternatives(
                        email_subject,
                        "",
                        settings.DEFAULT_FROM_EMAIL,
                        [user.email],
                    )
                    msg.mixed_subtype = "related"
                    msg.attach_alternative(email_body, "text/html")

                    # Attach logo if exists
                    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.png')
                    if os.path.exists(logo_path):
                        from email.mime.image import MIMEImage
                        with open(logo_path, 'rb') as f:
                            img = MIMEImage(f.read())
                            img.add_header('Content-ID', '<logo.png>')
                            img.add_header('Content-Disposition', 'inline', filename='logo.png')
                            msg.attach(img)
                    else:
                        logger.warning(f"Logo file not found at {logo_path}")

                    async_send_resend_email(msg=msg)
                    logger.info(f"Debit notification email sent to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send email to {user.email}: {str(e)}")

            # Return JSON with receipt URL
            receipt_url = reverse("transaction_receipt", args=[unique_reference])
            return JsonResponse({
                "success": True,
                "message": "Transfer successful.",
                "redirect_url": receipt_url
            })

        except Exception as e:
            logger.error(f"Transfer failed for user {request.user.email}: {str(e)}")
            return JsonResponse({'success': False, 'message': f'Transfer failed: {str(e)}'}, status=500)

    else:
        context = {
            'beneficiaries': Beneficiary.objects.filter(user=request.user),
        }
        return render(request, 'dashboard/finances/transfer.html', context)

def get_payment_gateway(request):
    try:
        data = json.loads(request.body)
        currency = data.get('currency')
        if not currency:
            return JsonResponse({
                'status': 'error',
                'message': 'Currency is required'
            }, status=400)

        # Map USDT - TRC20 to USDT
        network = currency if currency != 'USDT - TRC20' else 'USDT'

        try:
            gateway = PaymentGateway.objects.get(network=network)
            qr_code_url = gateway.qr_code.url if gateway.qr_code else None
            return JsonResponse({
                'status': 'success',
                'data': {
                    'network': gateway.network,
                    'deposit_address': gateway.deposit_address,
                    'instructions': gateway.instructions or 'No instructions provided.',
                    'qr_code': qr_code_url
                }
            })
        except PaymentGateway.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': f'No payment gateway found for {network}'
            }, status=404)

    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request format'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'An error occurred: {str(e)}'
        }, status=500)



VALID_CURRENCIES = ['USDT', 'USD', 'GBP', 'EUR']
VALID_PAYMENT_METHODS = ['bank_transfer', 'crypto']
def deposit_transaction_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            account = data.get('account')
            raw_amount = data.get('amount')
            currency = data.get('currency')
            payment_method = data.get('payment_method')

            # Validate required fields
            required_fields = ['account', 'amount', 'currency', 'payment_method']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({
                        'status': 'error',
                        'message': f'{field.replace("_", " ").title()} is required'
                    }, status=400)

            # Validate amount
            try:
                amount = Decimal(raw_amount)
                if amount < 0.01:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'Amount must be at least 0.01'
                    }, status=400)
            except (TypeError, ValueError, InvalidOperation):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid amount format'
                }, status=400)

            # Validate account
            valid_accounts = [choice[0] for choice in Deposit._meta.get_field('account').choices]
            if account not in valid_accounts:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid account type selected'
                }, status=400)

            # Validate currency and payment method
            if currency not in VALID_CURRENCIES:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid currency selected'
                }, status=400)
            if payment_method not in VALID_PAYMENT_METHODS:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid payment method selected'
                }, status=400)

            # Handle network for crypto payments
            network = None
            if payment_method == 'crypto':
                network = currency if currency != 'USDT - TRC20' else 'USDT'
                valid_networks = PaymentGateway.objects.values_list('network', flat=True)
                if network not in valid_networks:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'No payment gateway found for {network}'
                    }, status=404)

            # Atomic transaction
            with transaction.atomic():
                # Update balance for bank_transfer
                if payment_method == 'bank_transfer':
                    try:
                        balance = AccountBalance.objects.get(account=request.user)
                        balance_field_map = {
                            'Savings_Account': 'available_balance',
                            'Checking_Account': 'checking_balance',
                            'Loan_Account': 'loan_balance',
                            'GBP_Account': 'gbp',
                            'EUR_Account': 'eur'
                        }
                        balance_field = balance_field_map.get(account)
                        if not balance_field:
                            return JsonResponse({
                                'status': 'error',
                                'message': 'Invalid account type for balance update'
                            }, status=400)
                        current_balance = getattr(balance, balance_field, Decimal('0.00'))
                        setattr(balance, balance_field, current_balance + amount)
                        balance.total_credits = balance.total_credits + amount
                        balance.save()
                    except AccountBalance.DoesNotExist:
                        return JsonResponse({
                            'status': 'error',
                            'message': 'Account balance not found. Please contact support.'
                        }, status=400)

                # Create deposit record
                unique_reference = str(uuid.uuid4())
                deposit = Deposit.objects.create(
                    user=request.user,
                    amount=amount,
                    TNX=unique_reference,
                    network=network,
                    rate=Decimal('1.00'),  # Adjust if rate logic is implemented
                    account=account,
                    status='completed' if payment_method == 'bank_transfer' else 'pending'
                )

                # Create transaction record
                Transaction.objects.create(
                    user=request.user,
                    amount=amount,
                    transaction_type='deposit',
                    description=f"Deposit via {payment_method.upper()}",
                    status='pending' if payment_method != 'bank_transfer' else 'completed',
                    reference=unique_reference,
                    institution=payment_method,
                    to_account=account,
                    from_account=getattr(request.user, 'account_number', 'N/A')
                )

            return JsonResponse({
                'status': 'success',
                'message': f'Deposit request submitted successfully. Transaction ID: {deposit.TNX}',
            })

        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid request format'
            }, status=400)
        except Exception as e:
            logger.error(f"Deposit failed for user {request.user.email}: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f'An error occurred: {str(e)}'
            }, status=500)

    else:
        transactions = Deposit.objects.filter(user=request.user).order_by('-date')[:10]
        return render(request, 'Dashboard/finances/deposit.html', {'transactions': transactions})



@login_required
def loan_request(request):
    if request.method != "POST":
        return JsonResponse({
            "status": "error",
            "message": "Invalid request method."
        }, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))

        amount = data.get("amount")
        currency = data.get("currency", "USD")
        loan_type = data.get("loan_type", "personal")
        reason = data.get("reason")
        term_months = data.get("term_months")

        if not amount or not reason:
            return JsonResponse({
                "status": "error",
                "message": "Amount and reason are required."
            }, status=400)

        loan = LoanRequest.objects.create(
            user=request.user,
            amount=amount,
            currency=currency,
            loan_type=loan_type,
            reason=reason,
            term_months=term_months,
            status="pending",
            date=now()
        )

        return JsonResponse({
            "status": "success",
            "message": "Your loan request has been submitted successfully and is pending review.",
            "loan_id": loan.id
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Something went wrong: {str(e)}"
        }, status=500)
  

def account(request):
    if request.method == 'POST':
        try:
            print(f"POST data: {request.POST}")
            print(f"FILES data: {request.FILES}")

            user = request.user

            # ================= Profile Update =================
            if 'update_profile' in request.POST or any(
                key in request.POST for key in ['full_name', 'email', 'phone_number', 'country', 'city', 'gender']
            ):
                # ✅ Handle profile picture (field is 'profile_pic' in your form)
                if 'profile_pic' in request.FILES:
                    profile_pic = request.FILES['profile_pic']
                    if profile_pic.size > 5 * 1024 * 1024:  # 5MB limit
                        return JsonResponse({'error': 'Profile picture must be under 5MB'}, status=400)
                    user.profile_pic = profile_pic  # assumes your User model has profile_pic field

                # ✅ Handle profile details
                full_name = request.POST.get('full_name', '').strip()
                if full_name:
                    names = full_name.split(maxsplit=1)
                    user.first_name = names[0]
                    user.last_name = names[1] if len(names) > 1 else ''

                email = request.POST.get('email', user.email)
                if email != user.email and user.__class__.objects.filter(email=email).exists():
                    return JsonResponse({'error': 'Email already in use'}, status=400)
                user.email = email

                phone_number = request.POST.get('phone_number', user.phone_number)
                if phone_number and not re.match(r'^\+?[0-9]{10,15}$', phone_number):
                    return JsonResponse({'error': 'Invalid phone number format'}, status=400)
                user.phone_number = phone_number

                user.country = request.POST.get('country', user.country)
                user.city = request.POST.get('city', user.city)
                user.gender = request.POST.get('gender', user.gender)

                # ✅ Save only updated fields
                update_fields = ["first_name", "last_name", "email", "phone_number", "country", "city", "gender"]
                if 'profile_pic' in request.FILES:
                    update_fields.append("profile_pic")

                user.save(update_fields=update_fields)
                print(f"Profile updated for user: {user.email}")

                return JsonResponse({'success': True, 'message': 'Profile updated successfully'})

            # ================= Password Update =================
            elif 'change_password' in request.POST:
                old_password = request.POST.get('old_password')
                new_password1 = request.POST.get('new_password1')
                new_password2 = request.POST.get('new_password2')

                if not old_password:
                    return JsonResponse({'error': 'Current password is required'}, status=400)
                if not user.check_password(old_password):
                    return JsonResponse({'error': 'Current password is incorrect'}, status=400)
                if len(new_password1) < 6:
                    return JsonResponse({'error': 'New password must be at least 6 characters'}, status=400)
                if new_password1 != new_password2:
                    return JsonResponse({'error': 'New passwords do not match'}, status=400)

                user.set_password(new_password1)
                user.save(update_fields=["password"])
                update_session_auth_hash(request, user)
                print(f"Password updated for user: {user.email}")

                return JsonResponse({'success': True, 'message': 'Password updated successfully'})

            else:
                return JsonResponse({'error': 'Invalid request: missing required fields'}, status=400)

        except Exception as e:
            print(f"Unexpected error in account view: {str(e)}")
            return JsonResponse({'error': 'Server error occurred'}, status=500)

    # GET request → render profile page
    return render(request, 'dashboard/profile.html', {
        'user': request.user
    })
