"""Payment models."""

from django.conf import settings
from django.core.validators import MaxLengthValidator
from django.db import models
from uuid6 import uuid7


class CreditPackage(models.Model):
    """Available credit packages for purchase."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    name = models.CharField(max_length=100)
    credits = models.PositiveIntegerField()
    price = models.PositiveIntegerField(help_text="Price in TWD (integer)")
    description = models.TextField(
        blank=True,
        default="",
        validators=[MaxLengthValidator(500)],
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "credit_packages"
        ordering = ["sort_order", "price"]
        verbose_name = "credit package"
        verbose_name_plural = "credit packages"
        indexes = [
            models.Index(fields=["is_active", "sort_order"], name="pkg_active_sort_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.credits} credits / ${self.price})"


class CreditBalance(models.Model):
    """User's current credit balance."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="credit_balance",
    )
    balance = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "credit_balances"
        verbose_name = "credit balance"
        verbose_name_plural = "credit balances"

    def __str__(self) -> str:
        return f"{self.user}: {self.balance} credits"


class OrderStatus(models.TextChoices):
    """Payment order status choices."""

    PENDING = "pending", "Pending"
    PAID = "paid", "Paid"
    FAILED = "failed", "Failed"


class PaymentOrder(models.Model):
    """Payment order tracking each ECPay transaction."""

    id = models.UUIDField(primary_key=True, default=uuid7, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_orders",
    )
    package = models.ForeignKey(
        CreditPackage,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    merchant_trade_no = models.CharField(max_length=20, unique=True, db_index=True)
    status = models.CharField(
        max_length=10,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )
    amount = models.PositiveIntegerField(
        help_text="TWD amount snapshot at order creation",
    )
    credits_awarded = models.PositiveIntegerField(
        help_text="Credits snapshot at order creation",
    )
    ecpay_trade_no = models.CharField(max_length=20, blank=True, default="")
    payment_date = models.DateTimeField(null=True, blank=True)
    rtn_code = models.CharField(max_length=10, blank=True, default="")
    rtn_msg = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payment_orders"
        ordering = ["-created_at"]
        verbose_name = "payment order"
        verbose_name_plural = "payment orders"
        indexes = [
            models.Index(fields=["user", "-created_at"], name="order_user_created_idx"),
            models.Index(fields=["status"], name="order_status_idx"),
        ]

    def __str__(self) -> str:
        return f"Order {self.merchant_trade_no} - {self.status}"
