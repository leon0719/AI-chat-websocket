"""Payment tests."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import RequestFactory

from apps.payments.ecpay import (
    build_payment_form_html,
    ecpay_url_encode,
    generate_check_mac_value,
    verify_check_mac_value,
)
from apps.payments.models import CreditBalance, CreditPackage, OrderStatus, PaymentOrder
from apps.payments.services import (
    create_payment_order,
    generate_merchant_trade_no,
    get_user_balance,
    get_user_orders,
    process_ecpay_callback,
)
from apps.payments.views import ecpay_notify_view

SKILL_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "skills" / "ecpay"
TEST_VECTORS_PATH = SKILL_DIR / "test-vectors" / "checkmacvalue.json"

TEST_HASH_KEY = "pwFHCqoQZGmho4w6"
TEST_HASH_IV = "EkRm7iFT261dpevs"


@pytest.fixture
def credit_package(db):
    """Create a test credit package."""
    return CreditPackage.objects.create(
        name="Basic Pack",
        credits=100,
        price=300,
        description="100 credits for testing",
        is_active=True,
        sort_order=0,
    )


@pytest.fixture
def inactive_package(db):
    """Create an inactive credit package."""
    return CreditPackage.objects.create(
        name="Disabled Pack",
        credits=50,
        price=150,
        is_active=False,
    )


@pytest.fixture
def payment_order(user, credit_package):
    """Create a test payment order."""
    return PaymentOrder.objects.create(
        user=user,
        package=credit_package,
        merchant_trade_no="TEST12345678901234",
        amount=300,
        credits_awarded=100,
    )


# --- ECPay URL Encode Tests ---


class TestEcpayUrlEncode:
    def test_basic_encoding(self):
        result = ecpay_url_encode("hello world")
        assert "+" in result

    def test_tilde_encoding(self):
        """Python trap: quote_plus doesn't encode ~, must manually replace."""
        result = ecpay_url_encode("test~value")
        assert "~" not in result
        assert "%7e" in result

    def test_dotnet_replacements(self):
        """After lowercase, .NET special chars are restored."""
        result = ecpay_url_encode("a-b_c.d!e*f(g)")
        assert "-" in result
        assert "_" in result
        assert "." in result
        assert "!" in result
        assert "*" in result
        assert "(" in result
        assert ")" in result


# --- CheckMacValue Tests ---


class TestCheckMacValue:
    @pytest.mark.skipif(not TEST_VECTORS_PATH.exists(), reason="Test vectors file not found")
    def test_against_official_test_vectors(self):
        """Verify CMV generation against ECPay official test vectors."""
        with open(TEST_VECTORS_PATH) as f:
            data = json.load(f)

        for vector in data["vectors"]:
            if vector.get("formula") == "ecticket":
                continue

            method = vector["method"].lower()
            expected = vector["expected"]
            params = vector["params"]
            hash_key = vector["hashKey"]
            hash_iv = vector["hashIV"]

            if method == "sha256":
                result = generate_check_mac_value(params, hash_key, hash_iv)
            else:
                # MD5 not implemented in our ecpay.py (only SHA256 for AIO)
                continue

            assert result == expected, f"Failed vector: {vector['name']}"

    def test_generate_basic(self):
        params = {
            "MerchantID": "3002607",
            "MerchantTradeNo": "Test1234567890",
            "MerchantTradeDate": "2025/01/01 12:00:00",
            "PaymentType": "aio",
            "TotalAmount": "100",
            "TradeDesc": "測試",
            "ItemName": "測試商品",
            "ReturnURL": "https://example.com/notify",
            "ChoosePayment": "ALL",
            "EncryptType": "1",
        }
        result = generate_check_mac_value(params, TEST_HASH_KEY, TEST_HASH_IV)
        assert result == "291CBA324D31FB5A4BBBFDF2CFE5D32598524753AFD4959C3BF590C5B2F57FB2"

    def test_verify_valid(self):
        params = {
            "MerchantID": "3002607",
            "MerchantTradeNo": "Test1234567890",
            "RtnCode": "1",
            "RtnMsg": "Succeeded",
            "TradeNo": "2301011234567890",
            "TradeAmt": "100",
            "PaymentDate": "2025/01/01 12:05:00",
            "PaymentType": "Credit_CreditCard",
            "TradeDate": "2025/01/01 12:00:00",
            "SimulatePaid": "0",
            "CheckMacValue": "2AB536D86AFF8E1086744D59175040A32538C96B1C28C4135B551BD728E913B8",
        }
        assert verify_check_mac_value(params, TEST_HASH_KEY, TEST_HASH_IV)

    def test_verify_tampered(self):
        params = {
            "MerchantID": "3002607",
            "MerchantTradeNo": "Test1234567890",
            "RtnCode": "1",
            "CheckMacValue": "INVALID_HASH_VALUE",
        }
        assert not verify_check_mac_value(params, TEST_HASH_KEY, TEST_HASH_IV)

    def test_tilde_special_char(self):
        params = {
            "MerchantID": "3002607",
            "ItemName": "Test~Product",
            "TotalAmount": "200",
        }
        result = generate_check_mac_value(params, TEST_HASH_KEY, TEST_HASH_IV)
        assert result == "CEEAE01D2F9A8E74D4AC0DCE7735B046D73F35A5EC99558A31A2EE03159DA1C9"


# --- Payment Form Tests ---


class TestBuildPaymentFormHtml:
    def test_form_contains_required_fields(self, payment_order):
        html = build_payment_form_html(
            payment_order,
            merchant_id="3002607",
            hash_key=TEST_HASH_KEY,
            hash_iv=TEST_HASH_IV,
            payment_url="https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5",
            return_url="https://example.com/notify",
            client_back_url="https://example.com/return",
        )

        assert "MerchantID" in html
        assert "3002607" in html
        assert "MerchantTradeNo" in html
        assert payment_order.merchant_trade_no in html
        assert "CheckMacValue" in html
        assert "ChoosePayment" in html
        assert "Credit" in html
        assert "ecpay-form" in html
        assert "submit()" in html
        assert "payment-stage.ecpay.com.tw" in html


# --- Merchant Trade No Tests ---


class TestGenerateMerchantTradeNo:
    def test_length(self):
        trade_no = generate_merchant_trade_no()
        assert len(trade_no) == 20

    def test_uniqueness(self):
        trade_nos = {generate_merchant_trade_no() for _ in range(100)}
        assert len(trade_nos) == 100

    def test_alphanumeric(self):
        trade_no = generate_merchant_trade_no()
        assert trade_no.isalnum()


# --- Service Tests ---


class TestCreatePaymentOrder:
    @patch("apps.payments.services.app_settings")
    def test_creates_order(self, mock_settings, user, credit_package):
        mock_settings.ECPAY_MERCHANT_ID = "3002607"
        mock_settings.ECPAY_HASH_KEY = TEST_HASH_KEY
        mock_settings.ECPAY_HASH_IV = TEST_HASH_IV
        mock_settings.ECPAY_PAYMENT_URL = (
            "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
        )
        mock_settings.ECPAY_RETURN_URL = "https://example.com/notify"
        mock_settings.ECPAY_CLIENT_BACK_URL = "https://example.com/return"

        order, form_html = create_payment_order(user.id, credit_package.id)

        assert order.status == OrderStatus.PENDING
        assert order.amount == 300
        assert order.credits_awarded == 100
        assert order.user_id == user.id
        assert len(order.merchant_trade_no) == 20
        assert "<form" in form_html

    def test_inactive_package_raises(self, user, inactive_package):
        from apps.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            create_payment_order(user.id, inactive_package.id)


class TestProcessEcpayCallback:
    @patch("apps.payments.services.app_settings")
    def test_successful_payment(self, mock_settings, user, payment_order):
        mock_settings.ECPAY_HASH_KEY = TEST_HASH_KEY
        mock_settings.ECPAY_HASH_IV = TEST_HASH_IV

        params = {
            "MerchantID": "3002607",
            "MerchantTradeNo": payment_order.merchant_trade_no,
            "RtnCode": "1",
            "RtnMsg": "Succeeded",
            "TradeNo": "2301011234567890",
            "TradeAmt": "300",
            "PaymentDate": "2025/01/01 12:05:00",
            "PaymentType": "Credit_CreditCard",
            "TradeDate": "2025/01/01 12:00:00",
            "SimulatePaid": "0",
        }
        params["CheckMacValue"] = generate_check_mac_value(params, TEST_HASH_KEY, TEST_HASH_IV)

        result = process_ecpay_callback(params)

        assert result == "1|OK"
        payment_order.refresh_from_db()
        assert payment_order.status == OrderStatus.PAID
        assert payment_order.ecpay_trade_no == "2301011234567890"

        balance = CreditBalance.objects.get(user=user)
        assert balance.balance == 100

    @patch("apps.payments.services.app_settings")
    def test_idempotent_duplicate_callback(self, mock_settings, user, payment_order):
        mock_settings.ECPAY_HASH_KEY = TEST_HASH_KEY
        mock_settings.ECPAY_HASH_IV = TEST_HASH_IV

        # First: mark as paid
        payment_order.status = OrderStatus.PAID
        payment_order.save()
        CreditBalance.objects.create(user=user, balance=100)

        params = {
            "MerchantID": "3002607",
            "MerchantTradeNo": payment_order.merchant_trade_no,
            "RtnCode": "1",
            "RtnMsg": "Succeeded",
            "TradeNo": "2301011234567890",
            "TradeAmt": "300",
        }
        params["CheckMacValue"] = generate_check_mac_value(params, TEST_HASH_KEY, TEST_HASH_IV)

        result = process_ecpay_callback(params)
        assert result == "1|OK"

        # Balance should NOT increase (idempotent)
        balance = CreditBalance.objects.get(user=user)
        assert balance.balance == 100

    @patch("apps.payments.services.app_settings")
    def test_invalid_cmv(self, mock_settings, payment_order):
        mock_settings.ECPAY_HASH_KEY = TEST_HASH_KEY
        mock_settings.ECPAY_HASH_IV = TEST_HASH_IV

        params = {
            "MerchantTradeNo": payment_order.merchant_trade_no,
            "RtnCode": "1",
            "CheckMacValue": "INVALID",
        }
        result = process_ecpay_callback(params)
        assert result == "1|OK"

        payment_order.refresh_from_db()
        assert payment_order.status == OrderStatus.PENDING

    @patch("apps.payments.services.app_settings")
    def test_failed_payment(self, mock_settings, payment_order):
        mock_settings.ECPAY_HASH_KEY = TEST_HASH_KEY
        mock_settings.ECPAY_HASH_IV = TEST_HASH_IV

        params = {
            "MerchantID": "3002607",
            "MerchantTradeNo": payment_order.merchant_trade_no,
            "RtnCode": "10100058",
            "RtnMsg": "Failed",
            "TradeNo": "2301011234567890",
        }
        params["CheckMacValue"] = generate_check_mac_value(params, TEST_HASH_KEY, TEST_HASH_IV)

        result = process_ecpay_callback(params)
        assert result == "1|OK"

        payment_order.refresh_from_db()
        assert payment_order.status == OrderStatus.FAILED
        assert payment_order.rtn_code == "10100058"


class TestGetUserBalance:
    def test_new_user_gets_zero(self, user):
        balance = get_user_balance(user.id)
        assert balance == 0

    def test_existing_balance(self, user):
        CreditBalance.objects.create(user=user, balance=500)
        balance = get_user_balance(user.id)
        assert balance == 500


class TestGetUserOrders:
    def test_empty(self, user):
        orders, total, has_more = get_user_orders(user.id)
        assert orders == []
        assert total == 0
        assert has_more is False

    def test_with_orders(self, user, payment_order):
        orders, total, has_more = get_user_orders(user.id)
        assert len(orders) == 1
        assert orders[0].merchant_trade_no == payment_order.merchant_trade_no


# --- API Tests ---


class TestPaymentAPI:
    def test_list_packages(self, api_client, credit_package):
        response = api_client.get("/payments/packages")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Basic Pack"
        assert data[0]["credits"] == 100
        assert data[0]["price"] == 300

    def test_list_packages_excludes_inactive(self, api_client, credit_package, inactive_package):
        response = api_client.get("/payments/packages")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    @patch("apps.payments.services.app_settings")
    def test_create_order_authenticated(self, mock_settings, authenticated_client, credit_package):
        mock_settings.ECPAY_MERCHANT_ID = "3002607"
        mock_settings.ECPAY_HASH_KEY = TEST_HASH_KEY
        mock_settings.ECPAY_HASH_IV = TEST_HASH_IV
        mock_settings.ECPAY_PAYMENT_URL = (
            "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5"
        )
        mock_settings.ECPAY_RETURN_URL = "https://example.com/notify"
        mock_settings.ECPAY_CLIENT_BACK_URL = "https://example.com/return"

        response = authenticated_client.post(
            "/payments/orders",
            json={"package_id": str(credit_package.id)},
        )
        assert response.status_code == 201
        data = response.json()
        assert "form_html" in data
        assert "order_id" in data
        assert "<form" in data["form_html"]

    def test_create_order_unauthenticated(self, api_client, credit_package):
        response = api_client.post(
            "/payments/orders",
            json={"package_id": str(credit_package.id)},
        )
        assert response.status_code == 401

    def test_get_balance_authenticated(self, authenticated_client, user):
        response = authenticated_client.get("/payments/balance")
        assert response.status_code == 200
        assert response.json()["balance"] == 0

    def test_get_balance_unauthenticated(self, api_client):
        response = api_client.get("/payments/balance")
        assert response.status_code == 401

    def test_list_orders_authenticated(self, authenticated_client, user):
        response = authenticated_client.get("/payments/orders")
        assert response.status_code == 200
        data = response.json()
        assert data["orders"] == []
        assert data["total"] == 0


class TestEcpayNotifyView:
    @patch("apps.payments.services.app_settings")
    def test_callback_returns_1ok(self, mock_settings, payment_order):
        mock_settings.ECPAY_HASH_KEY = TEST_HASH_KEY
        mock_settings.ECPAY_HASH_IV = TEST_HASH_IV

        params = {
            "MerchantID": "3002607",
            "MerchantTradeNo": payment_order.merchant_trade_no,
            "RtnCode": "1",
            "RtnMsg": "Succeeded",
            "TradeNo": "2301011234567890",
            "TradeAmt": "300",
            "PaymentDate": "2025/01/01 12:05:00",
            "PaymentType": "Credit_CreditCard",
            "TradeDate": "2025/01/01 12:00:00",
            "SimulatePaid": "0",
        }
        params["CheckMacValue"] = generate_check_mac_value(params, TEST_HASH_KEY, TEST_HASH_IV)

        factory = RequestFactory()
        request = factory.post(
            "/api/payments/ecpay/notify",
            data=params,
            content_type="application/x-www-form-urlencoded",
        )

        response = ecpay_notify_view(request)
        assert response.status_code == 200
        assert response.content == b"1|OK"
        assert response["Content-Type"] == "text/plain"
