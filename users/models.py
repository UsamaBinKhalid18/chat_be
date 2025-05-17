"""Models for user app."""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from core.models import TimeStampedModel


class CustomUserManager(BaseUserManager):
    """Custom user manager for using email instead of username."""

    def create_user(self, email, password=None, **kwargs):
        """Create user with given params."""
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(email=self.normalize_email(email), **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_staff(self, email, password=None):
        """Create superuser with given params."""
        user = self.create_user(
            email=email,
            password=password,
        )
        user.is_staff = True
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None):
        """Create superuser with given params."""
        user = self.create_user(email=email, password=password)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user


class User(AbstractUser, TimeStampedModel):
    """Custom user model for using email instead of username."""

    username = None
    email = models.EmailField(verbose_name='email', max_length=60, unique=True)
    was_activated = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    @property
    def is_admin(self):
        return self.is_superuser or self.is_staff

    def save(self, *args, **kwargs):
        """Send activation email and create user profile."""
        if self.pk:
            return super().save(*args, **kwargs)

        is_social_account = getattr(self, 'is_social_account', False)
        is_staff_or_superuser = self.is_staff or self.is_superuser
        self.is_active = True
        self.was_activated = is_social_account or is_staff_or_superuser
        super().save(*args, **kwargs)
        UserProfile.objects.create(user=self)


class UserProfile(models.Model):
    """User profile for our custom user."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    stripe_customer_id = models.CharField(blank=True, null=True)
    free_requests = models.PositiveSmallIntegerField(default=3)
    last_free_request_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """String representation of model."""
        return self.user.email
