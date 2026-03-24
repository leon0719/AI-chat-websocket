"""Payment schemas."""

from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import Field


class CreditPackageSchema(Schema):
    """Credit package response schema."""

    id: UUID
    name: str = Field(min_length=1, max_length=100)
    credits: int = Field(ge=1)
    price: int = Field(ge=1)
    description: str = Field(max_length=500)


class CreateOrderSchema(Schema):
    """Create payment order request schema."""

    package_id: UUID


class PaymentFormSchema(Schema):
    """Payment form response with ECPay auto-submit HTML."""

    order_id: UUID
    merchant_trade_no: str = Field(min_length=1, max_length=20)
    form_html: str


class PaymentOrderSchema(Schema):
    """Payment order response schema."""

    id: UUID
    merchant_trade_no: str = Field(max_length=20)
    status: str = Field(max_length=10)
    amount: int = Field(ge=0)
    credits_awarded: int = Field(ge=0)
    package_name: str = Field(max_length=100)
    created_at: datetime
    payment_date: datetime | None = None

    @staticmethod
    def resolve_package_name(obj: object) -> str:
        return obj.package.name  # type: ignore[attr-defined]


class PaginatedOrdersSchema(Schema):
    """Paginated payment orders response."""

    orders: list[PaymentOrderSchema]
    total: int = Field(ge=-1)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    has_more: bool = False


class CreditBalanceSchema(Schema):
    """Credit balance response schema."""

    balance: int = Field(ge=0)
