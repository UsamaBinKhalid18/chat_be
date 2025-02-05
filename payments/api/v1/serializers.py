"""Serializers for Stripe APIs."""

from rest_framework import serializers

from payments.models import Package, UserSubscription


class PaymentModeEnum(serializers.ChoiceField):
    """Enum field for stripe payments and subscriptions."""

    def __init__(self, **kwargs):
        """Initialize enum fields."""
        super().__init__(choices=[('payment', 'Payment'), ('subscription', 'Subscription')], **kwargs)


class StripeProductSerializer(serializers.Serializer):
    """Serializer for handling products in Stripe."""

    id = serializers.IntegerField()
    quantity = serializers.IntegerField()


class StripeSerializer(serializers.Serializer):
    """Serialize data sent for Stripe payment."""

    mode = PaymentModeEnum()
    products_data = serializers.ListSerializer(child=StripeProductSerializer(), required=False)
    package_id = serializers.CharField(required=False)

    def validate(self, data):
        """Validate data for Stripe payments."""
        mode = data.get('mode')
        products_data = data.get('products_data')
        package_id = data.get('package_id')

        if mode == 'payment' and (not products_data or not len(products_data)):
            raise serializers.ValidationError("Products data is required for payment mode.")
        elif mode == 'subscription' and not package_id:
            raise serializers.ValidationError("Package ID is required for subscription mode.")

        return data


class PackageSerializer(serializers.ModelSerializer):
    """Packages serializer."""

    class Meta:
        model = Package
        fields = '__all__'


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """Serialize user subscriptions."""

    package = PackageSerializer()

    class Meta:
        model = UserSubscription
        fields = '__all__'
        read_only_fields = ('__all__', )
