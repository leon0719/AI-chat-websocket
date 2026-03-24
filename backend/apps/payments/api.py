"""Payment API endpoints."""

from ninja import Query, Router

from apps.payments.schemas import (
    CreateOrderSchema,
    CreditBalanceSchema,
    CreditPackageSchema,
    PaginatedOrdersSchema,
    PaymentFormSchema,
)
from apps.payments.services import (
    create_payment_order,
    get_user_balance,
    get_user_orders,
    list_active_packages,
)
from apps.users.auth import JWTAuth

router = Router()


@router.get("/packages", response=list[CreditPackageSchema])
def list_packages(request):
    """List available credit packages."""
    return list_active_packages()


@router.post("/orders", response={201: PaymentFormSchema}, auth=JWTAuth())
def create_order(request, payload: CreateOrderSchema):
    """Create a payment order and return ECPay auto-submit form HTML."""
    order, form_html = create_payment_order(
        user_id=request.auth.id,
        package_id=payload.package_id,
    )
    return 201, {
        "order_id": order.id,
        "merchant_trade_no": order.merchant_trade_no,
        "form_html": form_html,
    }


@router.get("/orders", response=PaginatedOrdersSchema, auth=JWTAuth())
def list_orders(
    request,
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(20, ge=1, le=100),
):
    """List payment orders for the current user."""
    orders, total, has_more = get_user_orders(request.auth.id, page, page_size)
    return {
        "orders": orders,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
    }


@router.get("/balance", response=CreditBalanceSchema, auth=JWTAuth())
def get_balance(request):
    """Get the current user's credit balance."""
    balance = get_user_balance(request.auth.id)
    return {"balance": balance}
