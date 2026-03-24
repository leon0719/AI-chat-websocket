"""ECPay callback view (CSRF-exempt, no auth).

This is a standalone Django view, not a Django Ninja endpoint,
because ECPay sends Server-to-Server POST without CSRF token.
"""

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.payments.services import process_ecpay_callback


@csrf_exempt
@require_POST
def ecpay_notify_view(request: HttpRequest) -> HttpResponse:
    """Handle ECPay ReturnURL callback.

    ECPay sends Form POST (application/x-www-form-urlencoded).
    Must respond with plain text "1|OK" and HTTP 200.
    """
    params = request.POST.dict()
    result = process_ecpay_callback(params)
    return HttpResponse(result, content_type="text/plain", status=200)
