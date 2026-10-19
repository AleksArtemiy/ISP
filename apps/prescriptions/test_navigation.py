from pathlib import Path

from django.conf import settings
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.test_support import Stage1DataMixin
from .models import Order
from .navigation import safe_next


class SafeNextTests(SimpleTestCase):
    def test_external_and_obfuscated_urls_rejected(self):
        for value in ("https://evil.test/", "http://evil.test/", "//evil.test/", "///evil.test/",
                      "javascript:alert(1)", "\\\\evil.test", "/\\evil.test", "/%2f/evil.test",
                      "/%0a/evil.test", "/%252f/evil.test", "https://testserver@evil.test/", "relative/path"):
            with self.subTest(value=value):
                request = RequestFactory().get("/", {"next": value})
                self.assertEqual(safe_next(request), "/prescriptions/")

    def test_same_host_is_normalized_to_local_url(self):
        for value in ("/institution/1/?q=a%26b", "http://testserver/institution/1/?q=a%26b"):
            self.assertEqual(safe_next(RequestFactory().get("/", {"next": value})), "/institution/1/?q=a%26b")
        self.assertEqual(safe_next(RequestFactory().get("/", {"next": "http://testserver/a"}, secure=True)), "/prescriptions/")

    def test_file_names_use_text_nodes(self):
        source = (settings.BASE_DIR / "apps/prescriptions/templates/prescriptions/order_form.html").read_text(encoding="utf-8")
        body = source.split("function updateFileList()", 1)[1].split("function getFileIcon", 1)[0]
        self.assertNotIn("innerHTML", body)
        self.assertIn("nameNode.textContent = file.name", body)


class NavigationFlowTests(Stage1DataMixin, TestCase):
    def payload(self, number="NEW-1", **extra):
        values = {"number": number, "institution": self.inst.pk, "authority": self.authority.pk,
                  "issue_date": "2026-01-01", "deadline_date": "2026-12-01", "status": "NEW",
                  "violations-TOTAL_FORMS": "1", "violations-INITIAL_FORMS": "0", "violations-0-text": "Текст"}
        values.update(extra)
        return values

    def setUp(self):
        self.client.force_login(self.committee)

    def test_detail_displays_the_actual_institution_name(self):
        response = self.client.get(reverse("prescriptions:order_detail", args=[self.order.pk]))
        self.assertContains(response, self.inst.name)
        self.assertNotContains(response, self.other_inst.name)

    def test_edit_preserves_dates_in_browser_date_inputs(self):
        for user in (self.committee, self.director):
            with self.subTest(user=user.email):
                self.client.force_login(user)
                response = self.client.get(reverse("prescriptions:order_update", args=[self.order.pk]))
                for field in ("issue_date", "deadline_date"):
                    value = getattr(self.order, field).isoformat()
                    self.assertContains(response, f'name="{field}" value="{value}"')

    def test_unsafe_next_not_echoed_in_links_or_hidden_inputs(self):
        for url in (reverse("prescriptions:order_create"), reverse("prescriptions:order_update", args=[self.order.pk]),
                    reverse("prescriptions:order_detail", args=[self.order.pk])):
            response = self.client.get(url, {"next": "javascript:alert(123)"})
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "javascript:alert(123)")
            self.assertEqual(response.context["next"], "/prescriptions/")

    def test_create_and_edit_redirect_to_validated_next(self):
        for value, expected in (("https://evil.test/", "/prescriptions/"), ("/institution/1/", "/institution/1/")):
            number = "NEW-" + str(Order.objects.count())
            response = self.client.post(reverse("prescriptions:order_create"), self.payload(number, next=value))
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response["Location"], expected)
            order = Order.objects.get(number=number)
            response = self.client.post(reverse("prescriptions:order_update", args=[order.pk]), self.payload(number, next=value))
            self.assertEqual(response["Location"], expected)

    def test_generic_edit_cannot_bypass_report_requirement(self):
        response = self.client.post(reverse("prescriptions:order_update", args=[self.order.pk]), self.payload(self.order.number, status="COMPLETED"))
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.status, "COMPLETED")
