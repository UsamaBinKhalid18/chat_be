
from django.urls import path
from payments.api.v1.views import CheckoutView, GetRemainingFreeRequests, UserSubscriptionsView
from payments.views.stripe import PaymentResponseWebhook


urlpatterns = [
    path('checkout/', CheckoutView.as_view(), name='checkout-api'),
    path('webhook/', PaymentResponseWebhook.as_view(), name='payment-response-webhook'),
    path('subscription/', UserSubscriptionsView.as_view(), name='subscription-api'),
    path('free-requests/', GetRemainingFreeRequests.as_view(), name='free-requests-api'),
]
