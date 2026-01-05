import random
from datetime import date, timedelta
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import AccountBalance, Card

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_account_balance(sender, instance, created, **kwargs):
    if created:
        AccountBalance.objects.create(account=instance)

def generate_card_number():
    """Generates a random 16-digit card number."""
    return "".join(str(random.randint(0, 9)) for _ in range(16))

def generate_card_password():
    """Generates a random 4-digit PIN."""
    return "".join(str(random.randint(0, 9)) for _ in range(4))

def random_expiry_date():
    """
    Generates a random expiry date between 2 and 5 years from today.
    (2 years = 730 days, 5 years = 1825 days)
    """
    return date.today() + timedelta(days=random.randint(730, 1825))

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_card(sender, instance, created, **kwargs):
    if created:
        Card.objects.create(
            user=instance,
            account=generate_card_number(),
            card_password=generate_card_password(),
            expiry_date=random_expiry_date(),
            vendor="mastercard",  # Always MasterCard
        )
