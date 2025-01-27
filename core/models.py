from django.db import models


class TimeStampedModel(models.Model):
    """Abstract model for timestamp fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta class for TimeStampedModel."""
        abstract = True
