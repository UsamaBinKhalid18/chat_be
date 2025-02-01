"""Stripe payment processor."""

import json
import logging
from datetime import datetime

import stripe
from django.contrib.auth import get_user_model

from payments.constants import CURRENCY_NAME
from payments.models import Invoice, Package, PaymentMethod, Refund, UserSubscription, Product
from payments.processors.base_processor import BasePaymentProcessor
from payments.emails import SubscriptionDeactivatedEmail
from users.models import UserProfile

User = get_user_model()
logger = logging.getLogger(__name__)


class Stripe(BasePaymentProcessor):
    """Payment processor logic for Stripe."""

    processor_name = 'stripe'
    event = ''
    status_map = {
        'succeeded': Refund.SUCCEEDED,
        'failed': Refund.FAILED,
        'pending': Refund.PENDING,
        'canceled': Refund.CANCELED
    }

    def __init__(self, *args, **kwargs):
        """Set Stripe API key."""
        super(Stripe, self).__init__(*args, **kwargs)
        stripe.api_key = self.processor_config['secret_key']

    def record_response(self, data, event=''):
        """Record processor response."""
        return super(Stripe, self).record_response(data, event=event or self.event)

    @staticmethod
    def _create_subscription_data(data):
        """Create checkout view for subscriptions."""
        package = Package.objects.get(id=data['package_id'])
        line_items = [{
            'price': package.stripe_price_id,
            'quantity': 1,
        }]

        return line_items, {}

    @staticmethod
    def _create_payment_data(data):
        """Create checkout view for subscriptions."""
        products_str = data['products_data']
        products_data = json.loads(products_str)

        product_ids = [product['id'] for product in products_data]
        products = Product.objects.in_bulk(product_ids)

        line_items = []
        products_metadata = []
        currency = CURRENCY_NAME.lower()

        for product in products_data:
            id = int(product['id'])
            name = products[id].name
            price = products[id].price

            line_items.append({
                'quantity': product['quantity'],
                'price_data': {
                    'currency': currency,
                    'product_data': {
                        'name': name,
                    },
                    'unit_amount': int(float(price)) * 100
                }
            })
            products_metadata.append({
                'name': name,
                'price': price,
                'quantity': product['quantity']
            })

        metadata = {
            'payment_intent_data': {'metadata': {
                'products': json.dumps(products_metadata),
            }}
        }

        return line_items, metadata

    def get_or_create_customer_id(self, user):
        """Create customer on Stripe if not already created."""
        profile = user.profile
        if profile.stripe_customer_id:
            return profile.stripe_customer_id
        customer = stripe.Customer.create(email=user.email)
        profile.stripe_customer_id = customer.id
        profile.save(update_fields=['stripe_customer_id'])
        return customer.id

    def create_checkout(self, request, data, *args, **kwargs):
        """Create checkout session for Stripe."""
        mode = data['mode']
        failure_url = self.get_failure_url(request)
        if mode == 'subscription':
            line_items, metadata = self._create_subscription_data(data)
        else:
            line_items, metadata = self._create_payment_data(data)
        try:
            checkout_session = stripe.checkout.Session.create(
                line_items=line_items,
                mode=mode,
                success_url=self.get_success_url(request),
                cancel_url=failure_url,
                customer=self.get_or_create_customer_id(request.user),
                **metadata
            )
            return {'checkout_page_url': checkout_session.url}
        except Exception as error:
            logger.error(error)
            return {'error': True, 'failure_url': failure_url}

    def handle_payment_response(self, response, data, *args, **kwargs):
        """Handle response from Stripe."""
        self.record_response(data)

    def _validate_customer_id(self, customer_id):
        """Check if customer id is valid."""
        if not customer_id:
            error_msg = 'No stripe customer id found'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def deactivate_subscription(self, customer_id, subscription_id, user_email, stripe_sub_id='', subscription=None):
        """Deactivate a stripe subscription."""
        self._validate_customer_id(customer_id)

        if not subscription:
            invoice = Invoice.get_from_subscription_id(subscription_id)

            if invoice and invoice.is_refund_allowed:
                return self.refund(invoice.id, invoice.user)

        try:
            if stripe_sub_id:
                user_subscription = UserSubscription.objects.get(subscription_id=stripe_sub_id)
            else:
                user_subscription = UserSubscription.objects.get(id=subscription_id)
            if not subscription:
                subscription = stripe.Subscription.retrieve(user_subscription.subscription_id)
        except stripe.error.InvalidRequestError:
            error_msg = f'No subscription with id {subscription_id} found in Stripe'
            logger.error(error_msg)
            raise ValueError(error_msg)
        except UserSubscription.DoesNotExist:
            error_msg = f'No subscription with id {subscription_id} found'
            logger.error(error_msg)
            raise ValueError(error_msg)

        if subscription.customer == customer_id:
            subscription.cancel()
            user_subscription.is_active = False
            user_subscription.save(update_fields=['is_active'])
        else:
            error_msg = f'No subscription with id {subscription_id} found for user {user_email}'
            logger.error(error_msg)
            raise ValueError(error_msg)

    def get_payment_method_for_user(self, customer_id, payment_method_id, user):
        """Get a payment method associated with a user."""
        self._validate_customer_id(customer_id)
        try:
            payment_method = PaymentMethod.objects.get(id=payment_method_id, user=user)
        except PaymentMethod.DoesNotExist:
            msg = f'No payment method found for id: {payment_method_id}'
            logger.error(msg)
            raise ValueError(msg)

        try:
            stripe_payment_method = stripe.Customer.retrieve_payment_method(
                customer_id, payment_method.payment_method_id
            )
        except stripe.error.InvalidRequestError:
            msg = f'No Stripe payment method with id {payment_method.payment_method_id} found for user {user.email}'
            logger.error(msg)
            raise ValueError(msg)

        return stripe_payment_method, payment_method

    def set_default_payment_method(self, customer_id, payment_method_id, user):
        """Set default payment method for a user."""
        _, payment_method = self.get_payment_method_for_user(customer_id, payment_method_id, user)
        if not payment_method.is_active:
            msg = f'Cannot set inactive payment method: {payment_method} as default!'
            logger.error(msg)
            raise ValueError(msg)
        if not payment_method.is_default:
            stripe.Customer.modify(
                customer_id, invoice_settings={'default_payment_method': payment_method.payment_method_id}
            )
            PaymentMethod.objects.filter(user=user, is_default=True).update(is_default=False)
            payment_method.is_default = True
            payment_method.save(update_fields=['is_default'])

    def delete_payment_method(self, customer_id, payment_method_id, user):
        """Delete a payment method for user."""
        stripe_payment_method, payment_method = self.get_payment_method_for_user(customer_id, payment_method_id, user)
        stripe.PaymentMethod.detach(stripe_payment_method.id)
        payment_method.is_active = False
        payment_method.save(update_fields=['is_active'])

    def get_subscriptions_from_line_items(self, line_items):
        """Fetch stripe subscriptions from line items."""
        data_to_update = {}
        for line in line_items:
            subscription = stripe.Subscription.retrieve(line.subscription)
            data_to_update[line.price.id] = subscription
        return data_to_update

    def create_payment_method(self, user, payment_method_id):
        """Create payment method for user."""
        payment_methods = PaymentMethod.objects.filter(user=user, is_active=True)
        if payment_methods.filter(payment_method_id=payment_method_id).exists():
            return
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        make_default = not payment_methods.filter(is_default=True).exists()
        PaymentMethod.objects.create(
            user=user,
            payment_processor=self.processor_name,
            payment_method_id=payment_method_id,
            card_brand=payment_method.card.brand,
            card_last_4_digits=payment_method.card.last4,
            is_default=make_default
        )
        return make_default

    def set_payment_method(self, payment_method):
        """Set payment method for a user."""
        customer_id = payment_method.customer
        try:
            user_profile = UserProfile.objects.get(stripe_customer_id=customer_id)
        except UserProfile.DoesNotExist:
            logger.error(f'No user found with stripe ID: {customer_id}')
            return
        make_default = self.create_payment_method(user_profile.user, payment_method.id)
        if make_default:
            stripe.Customer.modify(
                user_profile.stripe_customer_id, invoice_settings={'default_payment_method': payment_method.id}
            )

    def refund(self, invoice_id, user):
        """Refund subscription payments."""
        try:
            invoice = Invoice.objects.get(id=invoice_id, user=user)
        except Invoice.DoesNotExist:
            msg = f'No Invoice with id {invoice_id} found for user {user.email}'
            logger.error(msg)
            raise ValueError(msg)

        if not invoice.is_refund_allowed:
            raise ValueError('Refund not allowed!')

        subscription_id = invoice.payment_id

        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
        except stripe.error.InvalidRequestError:
            msg = f'No Stripe subscription with id {subscription_id} found'
            logger.error(msg)
            raise ValueError(msg)

        try:
            stripe_invoice = stripe.Invoice.retrieve(subscription.latest_invoice)
        except stripe.error.InvalidRequestError:
            msg = f'No Stripe invoice with id {subscription.latest_invoice} found'
            logger.error(msg)
            raise ValueError(msg)

        try:
            amount = int(invoice.amount) * 100
            refund = stripe.Refund.create(
                charge=stripe_invoice.charge, amount=amount, reason='requested_by_customer'
            )
            refund_obj = Refund.objects.create(
                invoice=invoice, amount=refund.amount / 100, object_id=refund.id, status=self.status_map[refund.status]
            )
        except stripe.error.InvalidRequestError as error:
            msg = f'Error creating refund with charge {stripe_invoice.charge}'
            logger.error(error)
            raise ValueError(msg)

        self.deactivate_subscription(
            user.profile.stripe_customer_id, 0, user.email, stripe_sub_id=subscription_id, subscription=subscription
        )
        return refund_obj

    @staticmethod
    def _parse_product_data(data):
        """Parse products data."""
        return json.loads(data['metadata']['products']), float(data['amount_received']) / 100

    @staticmethod
    def _parse_packages_data(items):
        """Parse data for packages."""
        line_items = []
        amount = 0

        for item in items:
            name = ''
            package = Package.objects.filter(stripe_price_id=item.price.id).first()
            price = item.price.unit_amount / 100
            amount += price

            if package:
                name = package.name
                amount = (amount - price) + package.price

            line_items.append({
                'price': price,
                'quantity': item.quantity,
                'name': name
            })
        return line_items, amount

    def get_line_items_data(self, data, mode=Invoice.PAYMENT):
        """Convert data to line items data."""
        if self.is_subscription:
            return self._parse_packages_data(dict(data.items())['items']['data'])
        return self._parse_product_data(data)

    def remove_subscription(self, subscription):
        """Unsubscribe user on platform."""
        try:
            user_profile = UserProfile.objects.get(stripe_customer_id=subscription.customer)
        except UserProfile.DoesNotExist:
            logger.error(f'User with stripe ID {subscription.customer} does not exist.')
            return

        stripe_ids = [item.price.id for item in dict(subscription.items())['items']['data']]
        UserSubscription.objects.filter(
            user=user_profile.user, is_active=True, package__stripe_price_id__in=stripe_ids
        ).update(is_active=False)

        packages = Package.objects.filter(stripe_price_id__in=stripe_ids)
        package_names = ','.join(packages.values_list('name', flat=True))

        subscription_deactivated_email = SubscriptionDeactivatedEmail()
        subscription_deactivated_email.send([user_profile.user.email], {'package_name': package_names})

    def create_or_update_user_subscriptions(self, data):
        """Create or update user subscription when invoice is charged."""
        data_to_update = self.get_subscriptions_from_line_items(data.lines.data)
        if data.billing_reason == 'subscription_cycle':
            subscriptions = UserSubscription.objects.filter(package__stripe_price_id__in=data_to_update.keys())
            for subscription in subscriptions:
                time_stamp = data_to_update[subscription.package.stripe_price_id].current_period_end
                subscription.current_period_end = datetime.fromtimestamp(time_stamp)
                subscription.is_active = True
            UserSubscription.objects.bulk_update(subscriptions)
        elif data.billing_reason == 'subscription_create':
            subscriptions = []
            user_profile = UserProfile.objects.get(stripe_customer_id=data.customer)
            for package_id in data_to_update.keys():
                current_period_end = datetime.fromtimestamp(data_to_update[package_id].current_period_end)
                subscriptions.append(UserSubscription(
                    user=user_profile.user,
                    package=Package.objects.get(stripe_price_id=package_id),
                    current_period_end=current_period_end,
                    subscription_id=data_to_update[package_id].id
                ))
            UserSubscription.objects.bulk_create(subscriptions)

    def provide_access_to_user(self, data):
        """Give access to user after successful subscription."""
        return self.create_or_update_user_subscriptions(data) if self.is_subscription else None

    def handle_failed_invoice(self, invoice):
        """Create or update an unpaid invoice."""
        self.record_response(invoice)
        if not invoice.subscription:
            return

        user_profile = UserProfile.objects.get(stripe_customer_id=invoice.customer)
        line_items_data, amount = self._parse_packages_data(invoice.lines.data)
        self.create_invoice(
            invoice.id, user_profile.user, amount, invoice.subscription, line_items_data,
            mode=Invoice.SUBSCRIPTION, status=Invoice.UNPAID
        )

    def handle_successful_payment(self, response, data, mode=Invoice.PAYMENT, *args, **kwargs):
        """Handle successful payment."""
        data = data.data.object
        mode = kwargs.get('mode', mode)
        description = data['description']
        is_subscription_intent = description and 'subscription' in description.lower()

        if mode == Invoice.PAYMENT and is_subscription_intent:
            return

        payment_id = data['id']
        user_profile = UserProfile.objects.get(stripe_customer_id=data['customer'])
        data.update({
            'user': user_profile.user,
            'payment_id': payment_id,
        })
        return super().handle_successful_payment(response, data, mode)
