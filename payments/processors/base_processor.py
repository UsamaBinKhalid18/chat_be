"""Base payment processor."""

import logging
from abc import ABC

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy

from payments.emails import PaymentSuccessfulEmail, PaymentUnsuccessfulEmail
from payments.models import Invoice, LineItem, PaymentProcessorResponse

User = get_user_model()

logger = logging.getLogger(__name__)


class BasePaymentProcessor(ABC):
    """Base class for implementing payment processors."""

    processor_name = ''
    success_url_name = 'success'
    failure_url_name = 'failure'
    is_subscription = False
    event = ''

    def __init__(self, *args, **kwargs):
        """Initialize attributes."""
        super(BasePaymentProcessor, self).__init__(*args, **kwargs)
        self.processor_config = settings.PAYMENT_PROCESSORS.get(self.processor_name, {})

        self.success_url = reverse_lazy(self.success_url_name)
        self.failure_url = reverse_lazy(self.failure_url_name)

        if settings.FRONTEND_PAYMENT_SUCCESS_URL:
            self.success_url = f'{settings.FRONTEND_BASE_URL}{settings.FRONTEND_PAYMENT_SUCCESS_URL}'
        if settings.FRONTEND_PAYMENT_FAILURE_URL:
            self.failure_url = f'{settings.FRONTEND_BASE_URL}{settings.FRONTEND_PAYMENT_FAILURE_URL}'

    def call_method(self, name, *args, **kwargs):
        """Use this method to call another method only if it exists."""
        if hasattr(self, name):
            method_to_call = getattr(self, name)
            return method_to_call(*args, **kwargs)
        raise ValueError(f'Action not found for {self.processor_name}')

    def record_response(self, data, event=''):
        """Record processor response."""
        PaymentProcessorResponse.objects.create(payment_processor=self.processor_name, event=event, response=data)

    def get_success_url(self, request):
        """Get success url."""
        if settings.FRONTEND_PAYMENT_SUCCESS_URL:
            return self.success_url
        return request.build_absolute_uri(self.success_url)

    def get_failure_url(self, request):
        """Get success url."""
        if settings.FRONTEND_PAYMENT_FAILURE_URL:
            return self.failure_url
        return request.build_absolute_uri(self.failure_url)

    def create_checkout(self, request, data, *args, **kwargs):
        """Create checkout page for payment processor."""
        raise NotImplementedError

    def handle_payment_response(self, response, data, *args, **kwargs):
        """Handle payment response for processor."""
        raise NotImplementedError

    def provide_access_to_user(self, data):
        """Give access to user after successful subscription."""
        raise NotImplementedError

    def get_line_items_data(self, data, mode=Invoice.PAYMENT):
        """Convert data to line items data."""
        raise NotImplementedError

    def create_invoice(
            self, invoice_id, user, amount, payment_id, line_items_data, mode=Invoice.PAYMENT,
            status=Invoice.PAID
    ):
        """Create invoice for successful payment."""
        new_invoice_id = invoice_id or payment_id
        try:
            invoice = Invoice.objects.get(object_id=new_invoice_id)
        except Invoice.DoesNotExist:
            invoice = Invoice.objects.create(
                object_id=new_invoice_id, user=user, amount=amount, payment_id=payment_id, mode=mode, status=status,
                payment_processor=self.processor_name,
            )
        line_items = []
        for line_item in line_items_data:
            line_item.pop('id', 0)
            line_items.append(LineItem(**line_item, invoice=invoice))
        LineItem.objects.bulk_create(line_items)
        return invoice

    def handle_successful_payment(self, response, data, mode=Invoice.PAYMENT, *args, **kwargs):
        """Handle successful payment."""
        user = data.pop('user')
        payment_id = data.pop('payment_id')
        self.is_subscription = mode == Invoice.SUBSCRIPTION
        line_items_data, amount = self.get_line_items_data(data, mode)
        invoice_id = data.latest_invoice if self.is_subscription else ''
        self.create_invoice(invoice_id, user, amount, payment_id, line_items_data, mode)

        payment_successful_email = PaymentSuccessfulEmail()
        payment_successful_email.send([user.email], {'line_items': line_items_data, 'amount': amount})

        return redirect(self.get_success_url(response))

    def handle_unsuccessful_payment(self, response, data):
        """Handle unsuccessful payment."""
        self.record_response(data=data, event=self.event)

        user_email = User.objects.get(profile__stripe_customer_id=data['data']['object']['customer']).email
        payment_unsuccessful_email = PaymentUnsuccessfulEmail()
        payment_unsuccessful_email.send([user_email], {})

        return redirect(self.get_failure_url(response))

    def handle_error(self, response, error, do_redirect=True):
        """Handle error in processing payment."""
        logger.error(error)
        if do_redirect:
            return self.handle_unsuccessful_payment(response, {'error', error})
        else:
            return JsonResponse({'error': str(error)}, status=400)

    def handle_payment(self, response, data, *args, **kwargs):
        """Handle payment response."""
        try:
            self.handle_payment_response(response, data, *args, **kwargs)
        except Exception as error:
            logger.error(error)
            return self.handle_unsuccessful_payment(response, data)

        return self.handle_successful_payment(response, data, *args, **kwargs)
