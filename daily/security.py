"""Security helpers for Chilavu: login rate limiting and extra browser security headers."""
import time

from django.core.cache import cache


# ---------- client IP ----------

def client_ip(request):
    """Best-effort client IP. Vercel puts the real client address in x-real-ip / x-forwarded-for."""
    ip = request.META.get("HTTP_X_REAL_IP") or ""
    if not ip:
        fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip = fwd.split(",")[0].strip() if fwd else ""
    return ip or request.META.get("REMOTE_ADDR", "") or "unknown"


# ---------- rate limiting (stops password guessing) ----------

class RateLimit:
    """Counts failed attempts in a shared cache.

    scope:   what is being protected ("signin", "forgot", "signup")
    limit:   attempts allowed inside `window` seconds
    """

    def __init__(self, scope, limit, window):
        self.scope, self.limit, self.window = scope, limit, window

    def _key(self, ident):
        return f"rl:{self.scope}:{ident}".lower()[:200]

    def blocked(self, *idents):
        """Seconds to wait if any identifier is over its limit, else 0."""
        now = time.time()
        wait = 0
        for ident in idents:
            data = cache.get(self._key(ident))
            if data and data["n"] >= self.limit:
                wait = max(wait, int(data["start"] + self.window - now))
        return max(wait, 0)

    def hit(self, *idents):
        now = time.time()
        for ident in idents:
            k = self._key(ident)
            data = cache.get(k)
            if not data or now - data["start"] > self.window:
                data = {"n": 0, "start": now}
            data["n"] += 1
            cache.set(k, data, self.window)

    def reset(self, *idents):
        for ident in idents:
            cache.delete(self._key(ident))


# 5 wrong passwords per account+device per 15 min, 30 per device per hour
SIGNIN_USER = RateLimit("signin-user", 5, 15 * 60)
SIGNIN_IP = RateLimit("signin-ip", 30, 60 * 60)
# recovery codes: 5 wrong tries per account per hour, 20 per device per hour
FORGOT_USER = RateLimit("forgot-user", 5, 60 * 60)
FORGOT_IP = RateLimit("forgot-ip", 20, 60 * 60)
# new accounts: 5 per device per hour
SIGNUP_IP = RateLimit("signup-ip", 5, 60 * 60)


def wait_message(seconds):
    mins = max(1, (seconds + 59) // 60)
    return f"Too many attempts. Please try again in {mins} minute{'s' if mins != 1 else ''}."


# ---------- security headers ----------

CSP = "; ".join([
    "default-src 'self'",
    # inline scripts/styles are used by the templates; external code is limited to known hosts
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
    "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com",
    "img-src 'self' data: blob:",
    "connect-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com",
    "manifest-src 'self'",
    "worker-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resp = self.get_response(request)
        resp.setdefault("Content-Security-Policy", CSP)
        resp.setdefault("Permissions-Policy", PERMISSIONS)
        # pages with personal data must not be stored by shared caches/proxies
        if request.user.is_authenticated and not request.path.startswith("/static/"):
            resp.setdefault("Cache-Control", "private, no-store")
        return resp
