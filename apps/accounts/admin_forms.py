from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError

from .throttling import release_login_attempt, reserve_login_attempt


class ThrottledAdminAuthenticationForm(AdminAuthenticationForm):
    """Use the same failure budget on Django's alternative login endpoint."""

    def clean(self):
        email = self.cleaned_data.get("username")
        if not email or not self.cleaned_data.get("password"):
            return super().clean()
        attempt = reserve_login_attempt(self.request, email)
        if attempt is None:
            raise ValidationError(
                "Слишком много попыток входа. Повторите через 15 минут.",
                code="rate_limited",
            )
        try:
            return super().clean()
        finally:
            # A valid password must not consume budget even if the account
            # lacks is_staff and the standard admin form rejects admission.
            if self.user_cache is not None:
                release_login_attempt(attempt)
