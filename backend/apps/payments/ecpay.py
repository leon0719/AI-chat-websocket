"""ECPay AIO payment client.

Handles CheckMacValue generation/verification and payment form building.
Protocol: CMV-SHA256 (CheckMacValue with SHA256 hash).

Source: ECPay skill guides/13-checkmacvalue.md §Python + guides/01-payment-aio.md
"""

import hashlib
import hmac
import html
import re
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

from apps.payments.models import PaymentOrder

TAIPEI_TZ = ZoneInfo("Asia/Taipei")

# Shell command keywords that ECPay WAF blocks in ItemName/TradeDesc
_WAF_KEYWORDS = re.compile(
    r"\b(echo|python|cmd|wget|curl|ping|net|telnet|bash|sh|powershell|exec|eval)\b",
    re.IGNORECASE,
)


def ecpay_url_encode(source: str) -> str:
    """ECPay-specific URL encoding (ecpayUrlEncode).

    Steps: urlencode → replace ~ → lowercase → .NET char replacements.
    Python trap: quote_plus() does not encode ~, must manually replace.
    """
    encoded = urllib.parse.quote_plus(source)
    encoded = encoded.replace("~", "%7E")
    encoded = encoded.lower()
    replacements = {
        "%2d": "-",
        "%5f": "_",
        "%2e": ".",
        "%21": "!",
        "%2a": "*",
        "%28": "(",
        "%29": ")",
    }
    for old, new in replacements.items():
        encoded = encoded.replace(old, new)
    return encoded


def generate_check_mac_value(
    params: dict[str, str],
    hash_key: str,
    hash_iv: str,
) -> str:
    """Generate CheckMacValue (SHA256) for ECPay AIO.

    Steps: filter CMV → sort by key (case-insensitive) → build string
    → ecpayUrlEncode → SHA256 → uppercase.
    """
    filtered = {k: v for k, v in params.items() if k != "CheckMacValue"}
    sorted_params = sorted(filtered.items(), key=lambda x: x[0].lower())
    param_str = "&".join(f"{k}={v}" for k, v in sorted_params)
    raw = f"HashKey={hash_key}&{param_str}&HashIV={hash_iv}"
    encoded = ecpay_url_encode(raw)
    hashed = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return hashed.upper()


def verify_check_mac_value(
    params: dict[str, str],
    hash_key: str,
    hash_iv: str,
) -> bool:
    """Verify CheckMacValue from ECPay callback using timing-safe comparison."""
    received = params.get("CheckMacValue", "")
    calculated = generate_check_mac_value(params, hash_key, hash_iv)
    return hmac.compare_digest(received.upper(), calculated)


def _sanitize_item_name(name: str) -> str:
    """Remove shell command keywords that trigger ECPay WAF."""
    sanitized = _WAF_KEYWORDS.sub("", name).strip()
    return sanitized[:200] if sanitized else "credit-topup"


def build_payment_form_html(
    order: PaymentOrder,
    *,
    merchant_id: str,
    hash_key: str,
    hash_iv: str,
    payment_url: str,
    return_url: str,
    client_back_url: str,
) -> str:
    """Build auto-submit HTML form for ECPay AIO payment.

    The browser will auto-submit this form, redirecting to ECPay's payment page.
    MerchantTradeDate uses UTC+8 (Asia/Taipei) as required by ECPay.
    """
    now_taipei = datetime.now(TAIPEI_TZ)
    item_name = _sanitize_item_name(order.package.name)

    params: dict[str, str] = {
        "MerchantID": merchant_id,
        "MerchantTradeNo": order.merchant_trade_no,
        "MerchantTradeDate": now_taipei.strftime("%Y/%m/%d %H:%M:%S"),
        "PaymentType": "aio",
        "TotalAmount": str(order.amount),
        "TradeDesc": "Credit Top-up",
        "ItemName": item_name,
        "ReturnURL": return_url,
        "ChoosePayment": "Credit",
        "EncryptType": "1",
    }

    if client_back_url:
        params["ClientBackURL"] = client_back_url

    params["CheckMacValue"] = generate_check_mac_value(params, hash_key, hash_iv)

    # Build HTML form with auto-submit
    fields = "\n".join(
        f'    <input type="hidden" name="{html.escape(k)}" value="{html.escape(v)}" />'
        for k, v in params.items()
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body>
  <form id="ecpay-form" method="POST" action="{html.escape(payment_url)}">
{fields}
  </form>
  <script>document.getElementById('ecpay-form').submit();</script>
</body>
</html>"""
