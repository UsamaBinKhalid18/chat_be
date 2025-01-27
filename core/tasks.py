"""Celery tasks for chat app."""

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template import loader


@shared_task()
def send_email(email_data):
    """Send emails."""
    email_message = EmailMultiAlternatives(
        email_data['subject'], email_data['body_text'], email_data['from_email_address'], email_data['recipients']
    )
    html_body_template_name = email_data['html_body_template_name']
    if html_body_template_name:
        html_email = loader.render_to_string(html_body_template_name, email_data['context'])
        email_message.attach_alternative(html_email, "text/html")
    email_message.send()
