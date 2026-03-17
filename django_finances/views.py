from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotFound, HttpResponseForbidden, HttpResponseBadRequest, HttpResponseServerError
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode


def _is_api_request(request):
    accept_header = request.headers.get("Accept", "")
    content_type = request.headers.get("Content-Type", "")
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    return (
        request.path.startswith("/finance/api/")
        or request.path.endswith(".json")
        or "application/json" in accept_header
        or "application/json" in content_type
        or is_ajax
    )


def _is_admin_request(request):
    return request.path.startswith("/admin/")


def _friendly_redirect(request, user_message, *, api_status=400, api_code="request_failed"):
    if _is_api_request(request):
        return JsonResponse(
            {"status": "error", "code": api_code, "message": user_message},
            status=api_status,
        )
    messages.error(request, user_message)
    if request.user.is_authenticated:
        return redirect("finance:transaction_list")
    login_url = reverse("login")
    next_url = reverse("finance:transaction_list")
    return redirect(f"{login_url}?{urlencode({'next': next_url})}")


def bad_request(request, exception):
    if _is_admin_request(request):
        return HttpResponseBadRequest()
    return _friendly_redirect(
        request,
        "Request was invalid. Please try again.",
        api_status=400,
        api_code="bad_request",
    )


def permission_denied(request, exception):
    if _is_admin_request(request):
        return HttpResponseForbidden()
    if _is_api_request(request):
        return JsonResponse(
            {"status": "error", "code": "permission_denied", "message": "Access denied."},
            status=403,
        )
    return _friendly_redirect(request, "You do not have permission for that action.")


def page_not_found(request, exception):
    if _is_admin_request(request):
        return HttpResponseNotFound()
    return _friendly_redirect(
        request,
        "Page not found. Redirected to dashboard.",
        api_status=404,
        api_code="not_found",
    )


def server_error(request):
    if _is_admin_request(request):
        return HttpResponseServerError()
    return _friendly_redirect(
        request,
        "Unexpected issue occurred. Please retry.",
        api_status=500,
        api_code="internal_error",
    )


def csrf_failure(request, reason=""):
    message = "Session expired. Please try again."
    if _is_api_request(request):
        return JsonResponse(
            {"status": "error", "code": "csrf_failed", "message": message},
            status=403,
        )
    messages.error(request, message)
    login_url = reverse("login")
    next_url = reverse("finance:transaction_list")
    return redirect(f"{login_url}?{urlencode({'next': next_url})}")
