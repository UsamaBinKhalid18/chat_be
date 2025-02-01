from rest_framework.permissions import IsAuthenticated


class IsAuthenticatedAndActivated(IsAuthenticated):
    """Permissions for URLs only accessible to authenticated and activated users."""

    def has_permission(self, request, view):
        """Check if user is authenticated and activated."""
        is_authenticated = super(IsAuthenticatedAndActivated, self).has_permission(request, view)
        return is_authenticated and request.user.is_active
