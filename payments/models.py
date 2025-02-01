"""Models for payments app."""

from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class Module(models.Model):
    """Modules in the project linked with packages."""

    name = models.CharField(max_length=25)
    description = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        """String representation for module."""
        return self.name


class BaseProduct(models.Model):
    """Base model for product and packages."""

    name = models.CharField(max_length=50)
    description = models.CharField(max_length=255)
    price = models.FloatField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        """String representation of package."""
        return f'{self.name} - {self.price}'


class Product(BaseProduct):
    """Products for purchase."""

    pass


class Package(BaseProduct):
    """Model containing packages for subscription."""

    stripe_price_id = models.CharField(max_length=50, null=True, default=None, blank=True)
    features = models.TextField()

    @staticmethod
    def get_user_packages(user):
        """Get list of modules accessible to users."""
        return Package.objects.filter(is_active=True, subscriptions__user=user, subscriptions__is_active=True)


class PaymentMethod(models.Model):
    """Payment Method data for users."""

    CARD = 0
    TYPES = [
        (CARD, _('Card')),
    ]

    user = models.ForeignKey(User, related_name='payment_methods', on_delete=models.CASCADE)
    payment_processor = models.CharField(max_length=50)
    payment_method_id = models.CharField(max_length=100)
    type = models.PositiveSmallIntegerField(choices=TYPES, default=CARD)
    card_brand = models.CharField(max_length=50)
    card_last_4_digits = models.PositiveSmallIntegerField()
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        """String representation for payment method."""
        return f'{self.user} - {self.payment_processor} - {self.get_type_display()} - {self.card_brand} - ' \
               f'{self.card_last_4_digits}'


class UserSubscription(models.Model):
    """Data for a user's purchased subscriptions."""

    user = models.ForeignKey(User, related_name='subscriptions', on_delete=models.CASCADE)
    package = models.ForeignKey(Package, related_name='subscriptions', on_delete=models.RESTRICT)
    current_period_end = models.DateField()
    subscription_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        """String representation for user subscriptions."""
        return f'{self.user.email} - {self.package.name} - {self.is_active}'


class Invoice(models.Model):
    """Invoice for purchased products or packages."""

    PAYMENT = 0
    SUBSCRIPTION = 1

    PAID = 0
    UNPAID = 1

    MODES = [
        (PAYMENT, _('Payment')),
        (SUBSCRIPTION, _('Subscription')),
    ]

    STATUSES = [
        (PAID, _('Paid')),
        (UNPAID, _('Unpaid'))
    ]

    object_id = models.CharField(max_length=50, blank=True, default='')
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='invoices')
    payment_processor = models.CharField(max_length=50)
    payment_id = models.CharField(max_length=50)
    amount = models.FloatField()
    mode = models.PositiveSmallIntegerField(choices=MODES)
    status = models.PositiveSmallIntegerField(choices=STATUSES, default=PAID)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """String representation of invoice."""
        return f'{self.user} - {self.payment_processor} - {self.amount} - {self.get_mode_display()}'

    @property
    def is_refund_allowed(self):
        """Check if refunds are allowed on this invoice."""
        try:
            allow_refund = self.refund == Refund.CANCELED or self.refund.status == Refund.FAILED
        except Refund.DoesNotExist:
            allow_refund = True

        return (
            self.status == Invoice.PAID
            and settings.REFUND_REQUEST_DAYS
            and self.mode == self.SUBSCRIPTION
            and allow_refund
            and self.created_at + timedelta(days=settings.REFUND_REQUEST_DAYS) > timezone.now()
        )

    @staticmethod
    def get_from_subscription_id(subscription_id):
        """Get Invoice using subscription ID."""
        try:
            subscription = UserSubscription.objects.get(id=subscription_id)
        except UserSubscription.DoesNotExist:
            return None
        return Invoice.objects.filter(payment_id=subscription.subscription_id).order_by('-created_at').first()


class LineItem(models.Model):
    """Line items for invoices."""

    name = models.CharField(max_length=50)
    price = models.FloatField()
    quantity = models.IntegerField()
    invoice = models.ForeignKey(Invoice, related_name='line_items', on_delete=models.CASCADE)

    def __str__(self):
        """String representation of line item."""
        return f'{self.name} - {self.price} - {self.quantity}'


class PaymentProcessorResponse(models.Model):
    """Data for payment processor response."""

    payment_processor = models.CharField(max_length=50)
    event = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    response = models.JSONField()

    def __str__(self):
        """String representation of class."""
        return f'{self.payment_processor} - {self.created_at}'


class Refund(models.Model):
    """Record data for refund."""

    PENDING = 0
    SUCCEEDED = 1
    FAILED = 2
    CANCELED = 3

    STATUSES = [
        (PENDING, _('Pending')),
        (SUCCEEDED, _('Succeeded')),
        (FAILED, _('Failed')),
        (CANCELED, _('Canceled'))
    ]

    invoice = models.OneToOneField(Invoice, on_delete=models.RESTRICT, related_name='refund')
    status = models.PositiveSmallIntegerField(choices=STATUSES)
    object_id = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)
    amount = models.FloatField()

    @staticmethod
    def get_refunds_for_user(user, processor_name=''):
        """List refunds for users."""
        refunds = Refund.objects.filter(invoice__user=user).order_by('-created_at')
        if processor_name:
            refunds = refunds.filter(invoice__payment_processor=processor_name)
        return refunds
