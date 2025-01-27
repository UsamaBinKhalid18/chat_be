"""Token generators for users."""

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class BaseTokenGenerator(PasswordResetTokenGenerator):
    """Generate token that will expire based on the given time."""

    timeout_seconds = 86400

    def check_token(self, user, token):
        """Check if the token is valid."""
        if not (user and token):
            return False
        try:
            ts_b36, _ = token.split('-')
        except ValueError:
            return False

        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False

        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(
                self._make_token_with_timestamp(user, ts, secret),
                token,
            ):
                break
        else:
            return False

        if (self._num_seconds(self._now()) - ts) > self.timeout_seconds:
            return False

        return True


class AccountActiveTokenGenerator(BaseTokenGenerator):
    """Token generator for activating accounts."""

    timeout_seconds = settings.ACTIVATION_EMAIL_TOKEN_EXPIRY_TIME

    def _make_hash_value(self, user, timestamp):
        """User user.is_active to generate a token that would be invalid after activation."""
        return f'{user.pk}{timestamp}{user.is_active}'
