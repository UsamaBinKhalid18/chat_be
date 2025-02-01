from core.email import BaseEmailMessage


class SubscriptionDeactivatedEmail(BaseEmailMessage):
    html_body_template_name = 'emails/subscription_deactivated.html'
    subject = 'Subscription Deactivated'


class PaymentSuccessfulEmail(BaseEmailMessage):
    html_body_template_name = 'emails/payment_successful.html'
    subject = 'Payment Successful'


class PaymentUnsuccessfulEmail(BaseEmailMessage):
    html_body_template_name = 'emails/payment_unsuccessful.html'
    subject = 'Payment Unsuccessful'
