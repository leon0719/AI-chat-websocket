"""Payment admin configuration."""

from django.contrib import admin

from apps.payments.models import CreditBalance, CreditPackage, PaymentOrder


@admin.register(CreditPackage)
class CreditPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "credits", "price", "is_active", "sort_order")
    list_filter = ("is_active",)
    list_editable = ("is_active", "sort_order")
    ordering = ("sort_order", "price")


@admin.register(CreditBalance)
class CreditBalanceAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "updated_at")
    readonly_fields = ("user", "balance")
    search_fields = ("user__email",)


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = (
        "merchant_trade_no",
        "user",
        "status",
        "amount",
        "credits_awarded",
        "created_at",
    )
    list_filter = ("status",)
    readonly_fields = (
        "id",
        "user",
        "package",
        "merchant_trade_no",
        "status",
        "amount",
        "credits_awarded",
        "ecpay_trade_no",
        "payment_date",
        "rtn_code",
        "rtn_msg",
        "created_at",
        "updated_at",
    )
    search_fields = ("merchant_trade_no", "user__email")
