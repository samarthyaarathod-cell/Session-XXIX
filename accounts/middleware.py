import time

from django.shortcuts import redirect


class BlockExpiredOTPAccessMiddleware:
    """Require a live OTP challenge before the verification page can be opened."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if getattr(request.resolver_match, "url_name", None) == "verify_otp":
            otp = request.session.get("otp")
            expires_at = request.session.get("otp_expires_at", 0)
            if not otp or time.time() >= expires_at:
                for key in ("otp", "otp_email", "otp_expires_at", "otp_attempts"):
                    request.session.pop(key, None)
                return redirect("forgot_password")
        return None
