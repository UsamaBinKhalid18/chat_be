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
