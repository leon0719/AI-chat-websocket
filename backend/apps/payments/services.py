"""Payment services."""

import secrets
import string
import time
from uuid import UUID

from django.db import transaction
from django.db.models import F

from apps.core.exceptions import ValidationError
from apps.core.log_config import logger
from apps.payments.ecpay import build_payment_form_html, verify_check_mac_value
from apps.payments.models import CreditBalance, CreditPackage, OrderStatus, PaymentOrder
from config.settings.base import settings as app_settings


def _get_ecpay_settings() -> dict[str, str]:
    """Get ECPay configuration from app settings."""
    return {
        "merchant_id": app_settings.ECPAY_MERCHANT_ID,
        "hash_key": app_settings.ECPAY_HASH_KEY,
        "hash_iv": app_settings.ECPAY_HASH_IV,
        "payment_url": app_settings.ECPAY_PAYMENT_URL,
        "return_url": app_settings.ECPAY_RETURN_URL,
        "client_back_url": app_settings.ECPAY_CLIENT_BACK_URL,
    }


def list_active_packages() -> list[CreditPackage]:
    """Return active credit packages ordered by sort_order."""
    return list(CreditPackage.objects.filter(is_active=True).order_by("sort_order", "price"))


def generate_merchant_trade_no() -> str:
    """Generate unique 20-char merchant trade number.

    Format: timestamp base36 (8 chars) + random alphanumeric (12 chars).
    """
    chars = string.ascii_uppercase + string.digits
    ts_part = ""
    n = int(time.time())
    while n > 0 and len(ts_part) < 8:
        ts_part = chars[n % 36] + ts_part
        n //= 36
    ts_part = ts_part.ljust(8, "0")
    rand_part = "".join(secrets.choice(chars) for _ in range(12))
    return ts_part + rand_part


def create_payment_order(user_id: UUID, package_id: UUID) -> tuple[PaymentOrder, str]:
    """Create a payment order and return (order, form_html).

    Snapshots package price/credits at creation time.
    """
    try:
        package = CreditPackage.objects.get(id=package_id, is_active=True)
    except CreditPackage.DoesNotExist as err:
        raise ValidationError("Invalid or inactive credit package") from err

    merchant_trade_no = generate_merchant_trade_no()

    order = PaymentOrder.objects.create(
        user_id=user_id,
        package=package,
        merchant_trade_no=merchant_trade_no,
        amount=package.price,
        credits_awarded=package.credits,
    )

    ecpay = _get_ecpay_settings()
    form_html = build_payment_form_html(
        order,
        merchant_id=ecpay["merchant_id"],
        hash_key=ecpay["hash_key"],
        hash_iv=ecpay["hash_iv"],
        payment_url=ecpay["payment_url"],
        return_url=ecpay["return_url"],
        client_back_url=ecpay["client_back_url"],
    )

    logger.info(
        f"Payment order created: trade_no={merchant_trade_no}, user={user_id}, amount={package.price}"
    )
    return order, form_html


def process_ecpay_callback(params: dict[str, str]) -> str:
    """Process ECPay ReturnURL callback.

    Verifies CheckMacValue, updates order status, awards credits atomically.
    Always returns "1|OK" to prevent ECPay retries.
    """
    ecpay = _get_ecpay_settings()

    if not verify_check_mac_value(params, ecpay["hash_key"], ecpay["hash_iv"]):
        logger.warning(
            f"ECPay callback CMV verification failed: trade_no={params.get('MerchantTradeNo', 'unknown')}"
        )
        return "1|OK"

    trade_no = params.get("MerchantTradeNo", "")
    rtn_code = params.get("RtnCode", "")
    rtn_msg = params.get("RtnMsg", "")

    with transaction.atomic():
        try:
            order = PaymentOrder.objects.select_for_update().get(merchant_trade_no=trade_no)
        except PaymentOrder.DoesNotExist:
            logger.warning(f"ECPay callback for unknown order: trade_no={trade_no}")
            return "1|OK"

        # Idempotency: already processed
        if order.status == OrderStatus.PAID:
            logger.info(f"ECPay callback duplicate (already paid): trade_no={trade_no}")
            return "1|OK"

        if order.status == OrderStatus.FAILED:
            logger.info(f"ECPay callback for failed order: trade_no={trade_no}")
            return "1|OK"

        order.ecpay_trade_no = params.get("TradeNo", "")
        order.rtn_code = rtn_code
        order.rtn_msg = rtn_msg

        # AIO RtnCode is STRING '1', not integer
        if rtn_code == "1":
            order.status = OrderStatus.PAID
            order.payment_date = params.get("PaymentDate")
            order.save(
                update_fields=[
                    "status",
                    "ecpay_trade_no",
                    "payment_date",
                    "rtn_code",
                    "rtn_msg",
                    "updated_at",
                ]
            )
            _award_credits(order.user_id, order.credits_awarded)
            logger.info(
                f"Payment successful: trade_no={trade_no}, "
                f"user={order.user_id}, credits={order.credits_awarded}"
            )
        else:
            order.status = OrderStatus.FAILED
            order.save(
                update_fields=[
                    "status",
                    "ecpay_trade_no",
                    "rtn_code",
                    "rtn_msg",
                    "updated_at",
                ]
            )
            logger.warning(
                f"Payment failed: trade_no={trade_no}, rtn_code={rtn_code}, rtn_msg={rtn_msg}"
            )

    return "1|OK"


def _award_credits(user_id: UUID, amount: int) -> None:
    """Atomically add credits to user's balance using F() expression."""
    balance, created = CreditBalance.objects.get_or_create(
        user_id=user_id,
        defaults={"balance": amount},
    )
    if not created:
        CreditBalance.objects.filter(user_id=user_id).update(balance=F("balance") + amount)


def get_user_balance(user_id: UUID) -> int:
    """Get user's credit balance, creating record if not exists."""
    balance, _ = CreditBalance.objects.get_or_create(
        user_id=user_id,
        defaults={"balance": 0},
    )
    return balance.balance


def get_user_orders(
    user_id: UUID,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PaymentOrder], int, bool]:
    """Get paginated payment orders for a user."""
    qs = (
        PaymentOrder.objects.select_related("package")
        .filter(user_id=user_id)
        .order_by("-created_at")
    )

    offset = (page - 1) * page_size
    orders = list(qs[offset : offset + page_size + 1])

    has_more = len(orders) > page_size
    orders = orders[:page_size]

    if page == 1 and not has_more:
        total = len(orders)
    else:
        total = -1

    return orders, total, has_more
