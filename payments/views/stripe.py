"""Views for Stripe payments."""

import logging

import stripe
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View

from payments.models import Invoice
from payments.processors.stripe import Stripe

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class PaymentResponseWebhook(View):
    """Web hook to handle payment response from stripe."""

    payment_processor = Stripe()

    def post(self, request):
        """Handle payment response from stripe."""
        payload = request.body
        signature_header = request.META['HTTP_STRIPE_SIGNATURE']

        try:
            event = stripe.Webhook.construct_event(
                payload, signature_header, self.payment_processor.processor_config['webhook_secret_key']
            )
        except ValueError as error:
            return self.payment_processor.handle_error(request, error, do_redirect=False)
        except stripe.error.SignatureVerificationError as error:
            return self.payment_processor.handle_error(request, error, do_redirect=False)

        event_id = event.id
        self.payment_processor.event = event.type
        print(event.type)

        if event.type == 'payment_method.attached':
            payment_method = event.data.object
            logger.info(f'Payment method attached for customer {payment_method.customer}')
            self.payment_processor.set_payment_method(payment_method)
        elif event.type == 'payment_intent.succeeded':
            logger.info(f'Payment intent succeeded: {event_id}')
            self.payment_processor.handle_payment(request, event, mode=Invoice.PAYMENT)
        elif event.type == 'customer.subscription.updated':
            logger.info(f'Subscription updated: {event_id}')
            self.payment_processor.handle_payment(request, event, mode=Invoice.SUBSCRIPTION)
        elif event.type == 'customer.subscription.deleted':
            logger.info(f'Subscription deleted: {event_id}')
            self.payment_processor.remove_subscription(event.data.object)
        elif event.type == 'invoice.payment_succeeded':
            logger.info(f'Payment charged for invoice {event.data.object.id}')
            self.payment_processor.provide_access_to_user(event.data.object)
        elif event.type == 'invoice.payment_failed':
            logger.info(f'Payment failed for invoice: {event.data.object.id}')
            self.payment_processor.handle_failed_invoice(event.data.object)
        elif event.type == 'payment_intent.payment_failed':
            logger.info(f'Payment failed: {event_id}')
            self.payment_processor.handle_unsuccessful_payment(request, event)
        else:
            logger.warning(f'Unhandled event type {event.type}')

        return JsonResponse({'success': True, 'safe': False})
