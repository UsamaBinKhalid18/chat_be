from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from users.emails import ForgetPasswordEmail, UserActivationEmail
from users.models import User
from users.utils import check_token, create_uid_and_token, get_user_from_uidb64


class UserSerializer(serializers.ModelSerializer):

    picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'is_active', 'picture']

    def get_picture(self, obj):
        if obj.socialaccount_set.first():
            return obj.socialaccount_set.first().extra_data.get('picture')
        return None


class LoginSerializer(TokenObtainPairSerializer):
    """Serializer for logging in user."""

    def validate(self, attrs):
        """Add user data after validation."""
        data = super().validate(attrs)
        data.update({
            'user': UserSerializer(self.user).data,
        })
        return data


class SignupSerializer(serializers.ModelSerializer):
    """Serializer for signing up user."""

    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'first_name', 'last_name']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def create(self, validated_data):
        """Create user."""
        user = User.objects.create_user(**validated_data, is_active=True, was_activated=False)
        UserActivationEmail().send(recipients=[user.email], user=user)
        return user


class RequestPasswordResetSerializer(serializers.Serializer):
    """Serializer for reset password request."""

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Check if user with this email exists."""
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('User with this email does not exist.')

        if not user.is_active:
            raise serializers.ValidationError('User is inactive.')

        self.user = user
        return value

    def send_mail(self, context, to_email):
        """Send a password reset email."""
        forget_password_email = ForgetPasswordEmail()
        forget_password_email.send([to_email], context)

    def save(
        self,
        token_generator=default_token_generator,
        extra_email_context=None,
    ):
        """Generate a one-use only link for resetting password and send it to the user."""

        email_field_name = User.get_email_field_name()
        user_email = getattr(self.user, email_field_name)
        uid, token = create_uid_and_token(self.user, token_generator=token_generator)
        context = {
            'email': user_email,
            'uid': uid,
            'token': token,
            **(extra_email_context or {}),
        }
        self.send_mail(context, user_email)


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for resetting password."""

    uidb64 = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(validators=[validate_password], write_only=True)

    def validate(self, attrs):
        """Validate token and user."""
        uidb64 = attrs.get('uidb64')
        token = attrs.get('token')

        try:
            user = get_user_from_uidb64(uidb64)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError('Invalid reset link.')

        if not check_token(user, token):
            raise serializers.ValidationError('Invalid reset link.')

        attrs['user'] = user
        return attrs

    def save(self, commit=True):
        """Update password."""
        password = self.validated_data['password']
        user = self.validated_data['user']
        user.set_password(password)
        if commit:
            user.save()
        return user
