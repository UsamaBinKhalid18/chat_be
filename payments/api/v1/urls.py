
from django.urls import path
from payments.api.v1.views import CheckoutView
from payments.views.stripe import PaymentResponseWebhook


urlpatterns = [
    path('checkout/', CheckoutView.as_view(), name='checkout-api'),
    path('webhook/', PaymentResponseWebhook.as_view(), name='payment-response-webhook')
]
