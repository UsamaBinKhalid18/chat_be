
import json
from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from payments.api.v1.serializers import StripeSerializer, UserSubscriptionSerializer
from payments.models import UserSubscription, Invoice
from payments.processors.stripe import Stripe
from users.permissions import IsAuthenticatedAndActivated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST


class CheckoutView(APIView):
    """Checkout view for redirecting to hosted checkout page depending on processor name."""

    permission_classes = (IsAuthenticatedAndActivated,)

    def _make_data(self, data):
        """Create data for Stripe processor based on payment mode."""
        mode = data['mode']
        stripe_data = {'mode': mode}
        if mode == 'payment':
            stripe_data['products_data'] = json.dumps(data['products_data'])
        else:
            stripe_data.update({
                'package_id': data['package_id']
            })
        return stripe_data

    def post(self, request):
        """Create stripe checkout session."""
        payment_processor = Stripe()
        serializer = StripeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response = payment_processor.create_checkout(request, self._make_data(serializer.data))
        if 'error' in response:
            return Response({'error': 'Error while processing data.'}, status=HTTP_400_BAD_REQUEST)
        return Response({'checkout_page_url': response['checkout_page_url']}, status=HTTP_200_OK)


class UserSubscriptionsView(APIView):
    """List user subscriptions."""

    serializer_class = UserSubscriptionSerializer
    permission_classes = (IsAuthenticatedAndActivated,)

    def get(self, request):
        """List subscriptions for user."""
        try:
            subscription = get_object_or_404(UserSubscription, is_active=True, user=request.user)
        except UserSubscription.MultipleObjectsReturned:
            subscription = UserSubscription.objects.filter(is_active=True, user=request.user).last()
        return Response(status=HTTP_200_OK, data=self.serializer_class(subscription).data)

    def post(self, request, *args, **kwargs):
        """Deactivate a user subscription."""
        customer_id = request.user.profile.stripe_customer_id
        subscription_id = request.data.get('subscription_id', '')

        invoice = Invoice.get_from_subscription_id(subscription_id)
        if not invoice:
            return Response({'error': 'No invoice attached with subscription'}, status=HTTP_400_BAD_REQUEST)
        payment_processor = Stripe()
        try:
            payment_processor.call_method('deactivate_subscription', customer_id, subscription_id, request.user.email)
        except ValueError as error:
            return Response({'error': error}, status=HTTP_400_BAD_REQUEST)

        return Response({'status': 'success'}, status=HTTP_200_OK)


class GetRemainingFreeRequests(APIView):
    """Get remaining free requests for user."""

    permission_classes = [IsAuthenticatedAndActivated]

    def get(self, request, *args, **kwargs):
        """Get free requests for user."""
        profile = request.user.profile
        if profile.last_free_request_at.date() != timezone.now().date():
            profile.free_requests = 3
            profile.save()
        return JsonResponse({'remaining_requests': request.user.profile.free_requests}, status=HTTP_200_OK)
