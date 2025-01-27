"""Django admin configuration for user app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from users.models import User


class UserAdmin(BaseUserAdmin):
    """Handle User admin."""

    list_display = (
        'email',
        'is_superuser',
        'is_staff',
    )
    fieldsets = (
        (
            None,
            {
                'fields': (
                    'first_name',
                    'last_name',
                    'email',
                    'password',
                )
            },
        ),
        (
            'Permissions',
            {
                'fields': (
                    'is_superuser',
                    'is_staff',
                )
            },
        ),
        (
            None,
            {
                'fields': (
                    'is_active',
                    'was_activated',
                )
            }
        )
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'password',
                    'confirm_password',
                ),
            },
        ),
    )
    ordering = ('id',)


admin.site.register(User, UserAdmin)
