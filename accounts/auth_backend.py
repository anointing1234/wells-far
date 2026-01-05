from django.contrib.auth.backends import BaseBackend
from .models import Account

class PinBackend(BaseBackend):
    """
    Custom authentication backend that allows login using
    Account ID or Email + login_pin instead of password.
    """

    def authenticate(self, request, account_id=None, login_pin=None, **kwargs):
        if account_id is None or login_pin is None:
            return None

        try:
            # Try finding by email first
            user = Account.objects.get(email=account_id)
        except Account.DoesNotExist:
            try:
                # If not found by email, try by account_id field
                user = Account.objects.get(account_id=account_id)
            except Account.DoesNotExist:
                return None

        # 🔎 Debug
        print("🔐 Stored hashed PIN:", user.login_pin)
        print("👀 Stored raw PIN:", user.raw_login_pin)
        print("📝 Provided login_pin:", login_pin)

        # First check hashed pin
        if user.check_login_pin(login_pin) and self.user_can_authenticate(user):
            return user

        # Fallback: check against raw_login_pin (only for debugging)
        if user.raw_login_pin == login_pin and self.user_can_authenticate(user):
            print("⚠️ Using raw PIN fallback!")
            return user

        return None

    def get_user(self, user_id):
        try:
            return Account.objects.get(pk=user_id)
        except Account.DoesNotExist:
            return None

    def user_can_authenticate(self, user):
        return getattr(user, "is_active", False)
