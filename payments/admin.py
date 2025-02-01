"""Admin configuration for payments app."""

from django.contrib import admin

from payments.models import (
    Invoice,
    LineItem,
    Module,
    Package,
    PaymentMethod,
    PaymentProcessorResponse,
    Product,
    Refund,
    UserSubscription
)


class PackageAdmin(admin.ModelAdmin):
    """Django admin configuration for modules."""


class LineItemInline(admin.TabularInline):
    """Show line items for invoice."""

    model = LineItem
    extra = 0
    can_delete = False

    def get_readonly_fields(self, request, obj=None):
        """Make line items read only."""
        if obj:
            return ['name', 'price', 'quantity']
        return []


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Configuration for Invoice on Django admin."""

    list_display = [
        'object_id', 'user', 'payment_processor', 'amount', 'get_status_display', 'get_mode_display', 'created_at'
    ]
    inlines = [LineItemInline]


admin.site.register(Package, PackageAdmin)
admin.site.register(Product)
admin.site.register(PaymentMethod)
admin.site.register(UserSubscription)
admin.site.register(PaymentProcessorResponse)
admin.site.register(Refund)
admin.site.register(Module)
