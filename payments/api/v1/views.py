import json
from rest_framework.views import APIView

from payments.api.v1.serializers import StripeSerializer
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
