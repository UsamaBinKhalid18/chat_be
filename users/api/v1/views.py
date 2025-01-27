from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from django.conf import settings
from django.http import JsonResponse
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from users.api.v1.serializers import RequestPasswordResetSerializer, ResetPasswordSerializer, SignupSerializer
from users.utils import activate_user, create_auth_data


class GoogleLoginView(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client


class SignupView(CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [AllowAny]


class ActivateUserAccount(APIView):
    """Activate a user's account."""

    def get(self, request, *args, **kwargs):
        """Activate a user using uid and token from URL."""
        was_activated, user = activate_user(kwargs.get('uidb64', ''), kwargs.get('token', ''))
        if not was_activated:
            return JsonResponse(data={'error': 'Token is invalid or expired '}, status=status.HTTP_400_BAD_REQUEST)

        data = create_auth_data(user)
        return JsonResponse(data=data, status=status.HTTP_200_OK)


class RequestPasswordResetView(APIView):
    """Send password reset based on front-end URL setting."""

    def post(self, request, *args, **kwargs):
        """Send password reset email based on front-end URL."""
        serializer = RequestPasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        extra_email_context = {'url': f'{settings.FRONTEND_BASE_URL}{settings.FRONTEND_PASSWORD_RESET_URL}'}

        serializer.save(extra_email_context=extra_email_context)
        return JsonResponse({'status': 'OK'}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """Reset user's password."""

    def post(self, request, *args, **kwargs):
        """Disable CSRF for API password reset."""
        serializer = ResetPasswordSerializer(data={
            **request.data,
            'uidb64': kwargs.get('uidb64', ''),
            'token': kwargs.get('token', ''),
        })
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return JsonResponse({'status': 'OK'}, status=status.HTTP_200_OK)
