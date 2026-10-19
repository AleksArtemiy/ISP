from urllib.parse import unquote, urlsplit, urlunsplit

from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def safe_next(request):
    """Return a local root-relative URL, shared by redirects, links and inputs."""
    fallback = reverse("prescriptions:order_list")
    raw = request.POST.get("next", "") if request.method == "POST" else request.GET.get("next", "")
    value = raw.strip()
    decoded = value
    for _ in range(3):
        decoded = unquote(decoded)
    if not value or decoded.startswith('//') or "\\" in decoded or any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        return fallback
    if not url_has_allowed_host_and_scheme(value, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return fallback
    parts = urlsplit(value)
    path = parts.path or "/"
    decoded_path = path
    for _ in range(3):
        decoded_path = unquote(decoded_path)
    if not path.startswith("/") or decoded_path.startswith("//"):
        return fallback
    return urlunsplit(("", "", path, parts.query, parts.fragment))
