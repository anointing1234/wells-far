from django import forms
from django.contrib.auth.forms import UserCreationForm
from accounts.models import Account,ACCOUNT_TYPE_CHOICES,Transfer,LoanRequest,Card,Beneficiary
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
import re
from django.contrib.auth import get_user_model
import random





def generate_unique_account_number():
    """
    Generate a unique 10-digit account number.
    """
    while True:
        acct_num = "".join(str(random.randint(0, 9)) for _ in range(10))
        if not Account.objects.filter(account_number=acct_num).exists():
            return acct_num

class SignupForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Enter your password',
                'type': 'password'
            }
        ),
        label="Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Confirm your password',
                'type': 'password'
            }
        ),
        label="Confirm Password"
    )

    class Meta:
        model = Account
        fields = [
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'account_type',
            'password',
        ]
        widgets = {
            'email': forms.EmailInput(
                attrs={
                    'class': 'form-control form-control-lg',
                    'placeholder': 'Enter your email',
                    'type': 'email'
                }
            ),
            'first_name': forms.TextInput(
                attrs={
                    'class': 'form-control form-control-lg',
                    'placeholder': 'First Name',
                    'type': 'text'
                }
            ),
            'last_name': forms.TextInput(
                attrs={
                    'class': 'form-control form-control-lg',
                    'placeholder': 'Last Name',
                    'type': 'text'
                }
            ),
            'phone_number': forms.TextInput(
                attrs={
                    'class': 'form-control form-control-lg',
                    'placeholder': 'Enter your phone number',
                    'type': 'number'
                }
            ),
            'account_type': forms.Select(
                attrs={
                    'class': 'form-select form-control-lg',
                },
                choices=Account.account_type  # Ensure this attribute exists on your Account model.
            ),
        }

    def clean(self):
        """Ensure both password fields match."""
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        """Save the user with a hashed password and auto-generate a unique account number."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        # Auto-generate and assign a unique account number if not already set.
        if not user.account_number:
            user.account_number = generate_unique_account_number()
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    account_id = forms.CharField(
        widget=forms.TextInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Enter your Account ID',
                'type': 'text'
            }
        ),
        label="Account ID"  # Set the label to "Account ID"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Enter your password',
                'type': 'password'
            }
        ),
        label=""
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Override the label_tag method for each bound field to return an empty string
        for bound_field in self.visible_fields():
            bound_field.label_tag = lambda **kwargs: ""

    def clean(self):
        account_id = self.cleaned_data.get('account_id')
        password = self.cleaned_data.get('password')

        # Authenticate with either email or account_id
        user = authenticate(username=account_id, password=password)
        if user is None:
            raise forms.ValidationError("Invalid Account ID or password.")
        self.user_cache = user
        return self.cleaned_data

    def get_user(self):
        return self.user_cache



def mask_account_number(account_number, account_type):
    """
    Mask the account number based on the account type.
    - For 'savings': shows '*******' followed by the last 5 digits.
    - For 'checking': shows '****' followed by the last 7 digits.
    - For 'gbp' or 'eur': mask all but the last 4 digits.
    """
    if not account_number:
        return ""
    if account_type == 'savings' and len(account_number) >= 5:
        return '*******' + account_number[-5:]
    elif account_type == 'checking' and len(account_number) >= 7:
        return '****' + account_number[-7:]
    else:
        # For gbp, eur, or any other type, mask all but the last 4 digits.
        return '*' * (len(account_number) - 4) + account_number[-4:]


class TransferForm(forms.ModelForm):
    # Existing beneficiary field.
    beneficiary = forms.ModelChoiceField(
        queryset=Beneficiary.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_beneficiary"})
    )
    # Manual beneficiary fields.
    new_full_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control manual-beneficiary-field",
            "placeholder": "Enter beneficiary full name"
        })
    )
    new_account_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control manual-beneficiary-field",
            "placeholder": "Enter beneficiary account number"
        })
    )
    new_bank_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control manual-beneficiary-field",
            "placeholder": "Enter beneficiary bank name"
        })
    )
    new_identifier_code = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control manual-beneficiary-field",
            "placeholder": "Enter SWIFT/BIC (optional)"
        })
    )
    new_routing_transit_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control manual-beneficiary-field",
            "placeholder": "Enter Routing Transit Number"
        })
    )
    new_bank_address = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control manual-beneficiary-field",
            "placeholder": "Enter Bank Address"
        })
    )
    
    # New field: From account dropdown.
    from_account = forms.ChoiceField(
        choices=[],  # Will be set dynamically in __init__
        widget=forms.Select(attrs={"class": "form-control", "required": True}),
        label="From"
    )

    pin = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter PIN"
        })
    )
    
    class Meta:
        model = Transfer
        # Remove "currency" and add "from_account" instead.
        fields = [
            "beneficiary", "amount", "reason", "region", "from_account"
        ]
        widgets = {
            "amount": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Enter amount",
                "step": "0.01",
                "required": True
            }),
            "reason": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Purpose of transfer",
                "required": True
            }),
            "region": forms.Select(
                choices=[
                    ("wire", "Wire Transfer"),
                    ("local", "Local Transfer"),
                    ("internal", "Internal Transfer")
                ],
                attrs={"class": "form-control", "required": True}
            ),
        }
    
    def __init__(self, *args, **kwargs):
        # Expect the current user (an Account instance) to be passed in.
        user = kwargs.pop('user', None)
        self.user = user
        super(TransferForm, self).__init__(*args, **kwargs)
        if user:
            self.fields['beneficiary'].queryset = Beneficiary.objects.filter(user=user)
            try:
                # Get the user's account balance.
                account_balance = user.account_balance
                # Retrieve balances.
                savings_balance = account_balance.available_balance
                checking_balance = account_balance.checking_balance
                gbp_balance = account_balance.gbp
                eur_balance = account_balance.eur
                
                # Use the user's account_number for masking (adjust if needed).
                account_number = user.account_number or ""
                
                # Create labels for each option.
                savings_label = f"Savings ({mask_account_number(account_number, 'savings')}) - ${savings_balance}"
                checking_label = f"Checking ({mask_account_number(account_number, 'checking')}) - ${checking_balance}"
                gbp_label = f"GBP ({mask_account_number(account_number, 'gbp')}) - £{gbp_balance}"
                eur_label = f"EUR ({mask_account_number(account_number, 'eur')}) - €{eur_balance}"
                
                # Define choices.
                choices = [
                    ('savings', savings_label),
                    ('checking', checking_label),
                    ('gbp', gbp_label),
                    ('eur', eur_label),
                ]
                self.fields['from_account'].choices = choices
            except Exception:
                # If account_balance is not available or another error occurs.
                self.fields['from_account'].choices = []
      
    def clean_pin(self):
        pin = self.cleaned_data.get('pin')
        if self.user and pin:
            # Assumes the user's model (Account) has a field named 'transaction_pin'.
            if self.user.pin != pin:
                raise ValidationError("Incorrect PIN.")
        return pin            
    

    def clean(self):
        cleaned_data = super().clean()
        beneficiary = cleaned_data.get('beneficiary')
        if not beneficiary:
            new_full_name = cleaned_data.get('new_full_name')
            new_account_number = cleaned_data.get('new_account_number')
            new_bank_name = cleaned_data.get('new_bank_name')
            new_routing_transit_number = cleaned_data.get('new_routing_transit_number')
            new_bank_address = cleaned_data.get('new_bank_address')
            # Require all beneficiary details if no existing beneficiary is selected.
            if not (new_full_name and new_account_number and new_bank_name and new_routing_transit_number and new_bank_address):
                raise forms.ValidationError(
                    "Please select an existing beneficiary or fill in all beneficiary details manually."
                )
        return cleaned_data
    
    def save(self, commit=True):
        transfer = super().save(commit=False)
        if not self.cleaned_data.get('beneficiary'):
            new_full_name = self.cleaned_data.get('new_full_name')
            new_account_number = self.cleaned_data.get('new_account_number')
            new_bank_name = self.cleaned_data.get('new_bank_name')
            new_identifier_code = self.cleaned_data.get('new_identifier_code')
            new_routing_transit_number = self.cleaned_data.get('new_routing_transit_number')
            new_bank_address = self.cleaned_data.get('new_bank_address')
            # Check if a beneficiary with these details already exists.
            existing_beneficiary = Beneficiary.objects.filter(
                user=self.user,
                full_name=new_full_name,
                account_number=new_account_number,
                bank_name=new_bank_name,
                routing_transit_number=new_routing_transit_number,
                bank_address=new_bank_address
            ).first()
            if existing_beneficiary:
                transfer.beneficiary = existing_beneficiary
            else:
                beneficiary = Beneficiary.objects.create(
                    user=self.user,
                    full_name=new_full_name,
                    account_number=new_account_number,
                    bank_name=new_bank_name,
                    swift_code=new_identifier_code,
                    routing_transit_number=new_routing_transit_number,
                    bank_address=new_bank_address
                )
                transfer.beneficiary = beneficiary
        # Save the chosen from_account (e.g., 'savings', 'checking', 'gbp', or 'eur').
        transfer.from_account = self.cleaned_data.get('from_account')
        if commit:
            transfer.save()
        return transfer




class LoanRequestForm(forms.ModelForm):
    class Meta:
        model = LoanRequest
        fields = ["amount", "currency", "loan_type", "reason", "term_months", "collateral"]
        widgets = {
            "amount": forms.NumberInput(attrs={"class": "form-control", "id": "loan_amount", "step": "0.01"}),
            "currency": forms.Select(attrs={"class": "form-control"}),
            "loan_type": forms.TextInput(attrs={"class": "form-control"}),
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "term_months": forms.NumberInput(attrs={"class": "form-control", "id": "term_months"}),
            "collateral": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount")
        term_months = cleaned_data.get("term_months")

        # Simple Interest Rate Calculation Logic (Adjust as Needed)
        if amount and term_months:
            if amount > 1000:
                interest_rate = 10.0  # 5% for small loans
            elif amount > 5000:
                interest_rate = 15.5  # 7.5% for medium loans
            else:
                interest_rate = 20.0  # 10% for large loans

            # Adjust based on loan duration
            if term_months > 12:
                interest_rate += 2  # Increase rate for longer terms

            # Set the calculated interest rate in the model
            cleaned_data["interest_rate"] = interest_rate

        return cleaned_data        




class CardForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ['account', 'card_type', 'vendor', 'status', 'card_password']
        widgets = {
            'card_password': forms.PasswordInput(),
        }        




class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Account  # Use your user model
        fields = ['email', 'country', 'city','gender']  # Add fields you want to edit







class SendresetcodeForm(forms.Form):
    email = forms.EmailField(
        max_length=100,
        help_text='Required. Enter your email address to receive a password reset code.'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set Bootstrap classes and placeholders
        self.fields['email'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your email'
        })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        User = get_user_model()  # Get the custom user model
        if not User.objects.filter(email=email).exists():
            raise ValidationError('No user is associated with this email address.')
        return email
    



class PasswordResetForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        help_text="Required. Enter your email address."
    )
    reset_code = forms.CharField(
        label="Reset Code",
        help_text="Required. Enter the reset code you received."
    )
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(),
        min_length=8,
        help_text="Required. Minimum length is 8 characters."
    )
    confirm_password = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(),
        help_text="Required. Please confirm your new password."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set Bootstrap classes and placeholders
        self.fields['email'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your email'
        })
        self.fields['reset_code'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your reset code'
        })
        self.fields['new_password'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your new password'
        })
        self.fields['confirm_password'].widget.attrs.update({
            'class': 'form-control form-control-lg',
            'placeholder': 'Confirm your new password'
        })

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            raise ValidationError("The two password fields must match.")

        return cleaned_data

