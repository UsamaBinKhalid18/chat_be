
from users.permissions import IsAuthenticatedAndActivated


class IsSubscribed(IsAuthenticatedAndActivated):
    """Permissions for URLs only accessible to authenticated and activated users."""

    def has_permission(self, request, view):
        """Check if user is authenticated and activated."""
        is_authenticated = super().has_permission(request, view)
        return is_authenticated and request.user.subscriptions.filter(is_active=True).exists()
