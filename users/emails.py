"""Emails required for users."""

from django.conf import settings

from core.email import BaseEmailMessage
from users.token_generators import AccountActiveTokenGenerator
from users.utils import create_uid_and_token


class ForgetPasswordEmail(BaseEmailMessage):
    """Class to send password reset emails."""

    html_body_template_name = 'emails/password_reset.html'
    subject = 'Password Reset for Chat app'


class UserActivationEmail(BaseEmailMessage):
    """Send activation link to user."""

    html_body_template_name = 'emails/activation_email.html'
    subject = 'Activate your account'

    def _serialize_data(self, recipients, context, *args, **kwargs):
        """Create URL for activation."""
        user = kwargs.get('user', None)
        uid, token = create_uid_and_token(user, token_generator=AccountActiveTokenGenerator())
        context['url'] = f'{settings.FRONTEND_BASE_URL}{settings.FRONTEND_ACTIVATION_URL}/{uid}/{token}'
        return super(UserActivationEmail, self)._serialize_data(recipients, context, *args, **kwargs)
