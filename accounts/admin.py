from django.contrib import admin, messages
from unfold.admin import ModelAdmin
from .models import (
    Account, AccountBalance,
    Transaction, Deposit, PaymentGateway,
    Beneficiary, Transfer, ResetPassword, TransferCode
)
from django.utils.html import format_html
from django.templatetags.static import static
from django import forms
from django.contrib.auth.hashers import make_password
import uuid
from django.db import transaction
from decimal import Decimal
from django.core.exceptions import ValidationError



class AdminUserCreationForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = [
            "email", "first_name", "last_name",
            "phone_number", "country", "city",
            "gender", "account_type"
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        base_username = user.email.split('@')[0][:5]
        user.username = f"{base_username}{str(uuid.uuid4().int)[:4]}"
        plain_login_pin = user.generate_random_number(6)
        plain_transaction_pin = user.generate_random_number(4)
        user.raw_login_pin = plain_login_pin
        user.raw_transaction_pin = plain_transaction_pin
        user.login_pin = make_password(plain_login_pin)
        user.transaction_pin = make_password(plain_transaction_pin)
        if commit:
            user.save()
        return user


class AdminUserChangeForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = '__all__'


@admin.register(Account)
class AccountAdmin(ModelAdmin):
    add_form = AdminUserCreationForm
    form = AdminUserChangeForm
    add_fieldsets = (
        ("Personal Info", {
            "fields": ("email", "first_name", "last_name", "phone_number", "gender")
        }),
        ("Account Details", {
            "fields": ("account_type", "country", "city")
        }),
    )
    fieldsets = (
        ("Personal Info", {
            "fields": ("profile_pic", "email", "username", "first_name", "last_name", "phone_number", "gender")
        }),
        ("Account Details", {
            "fields": ("account_type", "account_number", "country", "city", "status")
        }),
        ("Security", {
            "fields": ("raw_login_pin", "raw_transaction_pin", "password")
        }),
        ("Permissions", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")
        }),
    )
    list_display = (
        "profile_pic_preview",
        "account_id",
        "email",
        "account_type",
        "account_number",
        "status",
        "date_joined",
        "raw_login_pin",
        "raw_transaction_pin",
    )
    list_filter = ("account_id", "account_type", "status", "date_joined")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-date_joined",)
    readonly_fields = ("raw_login_pin", "raw_transaction_pin", "profile_pic_preview")

    def profile_pic_preview(self, obj):
        url = obj.profile_pic.url if obj.profile_pic else static('assets/images/user-grid-img13.png')
        return format_html('<img src="{}" style="width:50px; height:50px; border-radius:50%;" />', url)

    def get_form(self, request, obj=None, **kwargs):
        kwargs['form'] = self.add_form if obj is None else self.form
        return super().get_form(request, obj, **kwargs)

    def get_fieldsets(self, request, obj=None):
        return self.add_fieldsets if obj is None else super().get_fieldsets(request, obj)


@admin.register(AccountBalance)
class AccountBalanceAdmin(ModelAdmin):
    list_display = ("account", "loan_balance", "checking_balance", "gbp", "eur")
    exclude = ("available_balance",)   # 👈 hides field in edit form


@admin.register(Transaction)
class TransactionAdmin(ModelAdmin):
    list_display = ("user", "transaction_type", "amount", "status", "transaction_date")
    list_filter = ("transaction_type", "status", "transaction_date")
    search_fields = ("user__email", "reference")


@admin.register(Deposit)
class DepositAdmin(ModelAdmin):
    list_display = ("user", "amount", "account", "status", "date")
    list_filter = ("status", "account", "date")
    search_fields = ("user__email", "TNX")
    actions = ["confirm_deposit", "decline_deposit"]
    exclude = ("TNX",)

    @admin.action(description="Confirm selected deposits")
    def confirm_deposit(self, request, queryset):
        confirmed = 0
        with transaction.atomic():
            for deposit in queryset.filter(status="pending"):
                try:
                    balance = AccountBalance.objects.get(account=deposit.user)
                    balance_field_map = {
                        'Checking_Account': 'checking_balance',
                        'Loan_Account': 'loan_balance',
                        'GBP_Account': 'gbp',
                        'EUR_Account': 'eur'
                    }
                    balance_field = balance_field_map.get(deposit.account)
                    if balance_field:
                        current_balance = getattr(balance, balance_field, Decimal("0.00"))
                        setattr(balance, balance_field, current_balance + deposit.amount)
                        balance.total_credits += deposit.amount
                        balance.save()
                    deposit.status = "completed"
                    deposit.save(update_fields=["status"])
                    Transaction.objects.filter(
                        user=deposit.user,
                        reference=deposit.TNX,
                        transaction_type="deposit"
                    ).update(status="completed")
                    confirmed += 1
                except AccountBalance.DoesNotExist:
                    self.message_user(
                        request,
                        f"Balance not found for {deposit.user.email}. Skipping deposit {deposit.TNX}.",
                        level=messages.WARNING
                    )
        self.message_user(
            request,
            f"✅ {confirmed} deposits confirmed, balances updated, and transactions marked completed.",
            level=messages.SUCCESS
        )

    @admin.action(description="Decline selected deposits")
    def decline_deposit(self, request, queryset):
        declined = 0
        with transaction.atomic():
            for deposit in queryset.filter(status="pending"):
                deposit.status = "failed"
                deposit.save(update_fields=["status"])
                Transaction.objects.filter(
                    user=deposit.user,
                    reference=deposit.TNX,
                    transaction_type="deposit"
                ).update(status="failed")
                declined += 1
        self.message_user(
            request,
            f"❌ {declined} deposits declined and transactions marked failed.",
            level=messages.WARNING
        )

    def save_model(self, request, obj, form, change):
        if not change:
            with transaction.atomic():
                balance = AccountBalance.objects.get(account=obj.user)
                balance_field_map = {
                    'Checking_Account': 'checking_balance',
                    'Loan_Account': 'loan_balance',
                    'GBP_Account': 'gbp',
                    'EUR_Account': 'eur'
                }
                balance_field = balance_field_map.get(obj.account)
                if balance_field:
                    current_balance = getattr(balance, balance_field, Decimal("0.00"))
                    setattr(balance, balance_field, current_balance + obj.amount)
                    balance.total_credits += obj.amount
                    balance.save()
                obj.status = "completed"
                if not obj.TNX:
                    obj.TNX = str(uuid.uuid4())
                obj.save()
                reference = obj.TNX
                if Transaction.objects.filter(reference=reference).exists():
                    reference = str(uuid.uuid4())
                Transaction.objects.create(
                    user=obj.user,
                    amount=obj.amount,
                    transaction_type="deposit",
                    description=f"Admin deposit to {obj.account}",
                    status="completed",
                    reference=reference,
                    institution="admin",
                    to_account=obj.account,
                    from_account="ADMIN"
                )
        super().save_model(request, obj, form, change)


@admin.register(PaymentGateway)
class PaymentGatewayAdmin(ModelAdmin):
    list_display = ("network", "deposit_address")


@admin.register(Beneficiary)
class BeneficiaryAdmin(ModelAdmin):
    list_display = ("full_name", "bank_name", "account_number", "created_at")
    search_fields = ("full_name", "bank_name", "account_number")


class TransferAdminForm(forms.ModelForm):
    BALANCE_CHOICES = [
        ("Checking_Account", "Checking Account"),
        ("Loan_Account", "Loan Account"),
        ("GBP_Account", "GBP Account"),
        ("EUR_Account", "EUR Account"),
    ]
    balance = forms.ChoiceField(
        choices=BALANCE_CHOICES,
        label="Select Account",
        widget=forms.Select(
            attrs={
                "class": "vSelect",
                "style": (
                    "width: 250px;padding: 6px 12px;border: 1px solid #d1d5db;"
                    "border-radius: 0.375rem;background-color: #f9fafb;color: #111827;"
                    "font-size: 14px;outline: none;transition: border-color 0.2s, box-shadow 0.2s;"
                )
            }
        )
    )
    class Meta:
        model = Transfer
        fields = "__all__"


@admin.register(Transfer)
class TransferAdmin(ModelAdmin):
    form = TransferAdminForm
    list_display = (
        "reference", "user", "beneficiary_display", "amount", "balance",
        "status", "date"
    )
    list_filter = ("status", "balance", "date", "beneficiary")
    search_fields = (
        "reference",
        "user__username",
        "beneficiary__full_name",
        "beneficiary__bank_name",
        "beneficiary__account_number",
    )
    ordering = ("-date",)
    readonly_fields = ("reference", "charge")
    actions = ["approve_transfer", "reject_transfer"]
    fieldsets = (
        ("Transfer Details", {
            "fields": ("reference", "user", "beneficiary", "amount",
                       "balance", "charge", "reason", "status")
        }),
    )

    def save_model(self, request, obj, form, change):
        if not obj.reference:
            obj.reference = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        try:
            user_balance = AccountBalance.objects.get(account=obj.user)
        except AccountBalance.DoesNotExist:
            raise ValidationError("⚠️ This user does not have an account balance record.")
        amount = obj.amount
        account_type = obj.balance
        if account_type == "Checking_Account" and amount > user_balance.checking_balance:
            raise ValidationError("⚠️ Insufficient funds in Checking Account.")
        elif account_type == "Loan_Account" and amount > user_balance.loan_balance:
            raise ValidationError("⚠️ Insufficient funds in Loan Account.")
        elif account_type == "GBP_Account" and amount > user_balance.gbp:
            raise ValidationError("⚠️ Insufficient funds in GBP Account.")
        elif account_type == "EUR_Account" and amount > user_balance.eur:
            raise ValidationError("⚠️ Insufficient funds in EUR Account.")
        super().save_model(request, obj, form, change)
        if obj.status == "completed":
            self.confirm_single_transfer(obj)
        elif obj.status == "failed":
            self.cancel_single_transfer(obj)

    def beneficiary_display(self, obj):
        if obj.beneficiary:
            return format_html(
                "{}<br><small>{} - {}</small>",
                obj.beneficiary.full_name,
                obj.beneficiary.bank_name,
                obj.beneficiary.account_number,
            )
        return "-"
    beneficiary_display.short_description = "Beneficiary"

    def confirm_single_transfer(self, transfer):
        try:
            user_balance = AccountBalance.objects.get(account=transfer.user)
        except AccountBalance.DoesNotExist:
            raise ValidationError("⚠️ This user does not have an account balance record.")
        from_acc = "Unknown Account"
        if transfer.balance == "Checking_Account":
            user_balance.checking_balance -= transfer.amount
            from_acc = "Checking Account"
        elif transfer.balance == "Loan_Account":
            user_balance.loan_balance -= transfer.amount
            from_acc = "Loan Account"
        elif transfer.balance == "GBP_Account":
            user_balance.gbp -= transfer.amount
            from_acc = "GBP Account"
        elif transfer.balance == "EUR_Account":
            user_balance.eur -= transfer.amount
            from_acc = "EUR Account"
        user_balance.total_debits += transfer.amount
        user_balance.save()
        transfer.status = "completed"
        transfer.save()
        Transaction.objects.update_or_create(
            user=transfer.user,
            reference=transfer.reference,
            transaction_type="transfer",
            defaults={
                "amount": transfer.amount,
                "status": "completed",
                "description": transfer.reason or f"Transfer to {transfer.beneficiary.full_name if transfer.beneficiary else 'Unknown'}",
                "institution": transfer.beneficiary.bank_name if transfer.beneficiary else None,
                "region": transfer.region,
                "from_account": from_acc,
                "to_account": f"{transfer.beneficiary.full_name} - {transfer.beneficiary.account_number}" if transfer.beneficiary else None,
            }
        )

    def cancel_single_transfer(self, transfer):
        transfer.status = "failed"
        transfer.save()
        transaction = Transaction.objects.filter(
            user=transfer.user,
            reference=transfer.reference,
            transaction_type="transfer"
        ).first()
        if transaction:
            transaction.status = "failed"
            transaction.save()

    def approve_transfer(self, request, queryset):
        for transfer in queryset:
            if transfer.status == "pending":
                self.confirm_single_transfer(transfer)
        messages.success(request, "Selected transfers have been approved.")
    approve_transfer.short_description = "Approve selected transfers"

    def reject_transfer(self, request, queryset):
        for transfer in queryset:
            if transfer.status == "pending":
                self.cancel_single_transfer(transfer)
        messages.warning(request, "Selected transfers have been rejected.")
    reject_transfer.short_description = "Reject selected transfers"


@admin.register(ResetPassword)
class ResetPasswordAdmin(ModelAdmin):
    list_display = ("email", "reset_code", "created_at")
    search_fields = ("email",)


@admin.register(TransferCode)
class TransferCodeAdmin(ModelAdmin):
    list_display = ("user","freeze_code","tac_code", "tax_code", "atc_code", "created_at", "expires_at", "used")
    list_filter = ("used",)
    search_fields = ("user__email","freeze_code","tac_code", "tax_code", "atc_code")
