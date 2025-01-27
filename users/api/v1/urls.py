
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from users.api.v1.views import (
    ActivateUserAccount, GoogleLoginView, RequestPasswordResetView, ResetPasswordView, SignupView
)


urlpatterns = [
    path('login/', TokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('activate/<uidb64>/<token>/', ActivateUserAccount.as_view(), name='activate-user-api'),
    path('signup/', SignupView.as_view(), name='signup'),
    path('google/', GoogleLoginView.as_view(), name='google-api-login'),
    path('reset-password', RequestPasswordResetView.as_view(), name='reset-password-request'),
    path('reset-password/<uidb64>/<token>/', ResetPasswordView.as_view(), name='reset-password-confirm'),
]
