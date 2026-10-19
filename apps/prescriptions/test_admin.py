import tempfile
from pathlib import Path

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.test_support import Stage1DataMixin
from .models import File, Order, OrderViolation, Violation
from .test_files import pdf_upload
from .views import handle_uploaded_files


class BusinessAdminTests(Stage1DataMixin, TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.storage = Path(temporary.name)
        override = self.settings(MEDIA_ROOT=self.storage)
        override.enable()
        self.addCleanup(override.disable)
        handle_uploaded_files(self.order, [pdf_upload()], self.committee)
        self.file = File.objects.get(order=self.order)
        self.physical_file = self.storage / self.file.file_path
        self.original_bytes = self.physical_file.read_bytes()
        self.violation = Violation.objects.create(description="Историческое нарушение")
        self.link = OrderViolation.objects.create(order=self.order, violation=self.violation)
        self.staff = self.committee
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])
        self.staff.user_permissions.set(Permission.objects.filter(content_type__app_label="prescriptions"))

    def url(self, obj, action):
        return reverse(f"admin:prescriptions_{obj._meta.model_name}_{action}", args=[obj.pk])

    def objects(self):
        return (self.order, self.other_order, self.file, self.violation, self.link, self.authority)

    def assert_history_intact(self):
        self.order.refresh_from_db()
        self.file.refresh_from_db()
        self.assertEqual(self.order.created_by_user_id, self.committee.pk)
        self.assertEqual(self.order.status, "NEW")
        self.assertEqual(self.file.order_id, self.order.pk)
        self.assertEqual(self.file.uploaded_by_user_id, self.committee.pk)
        self.assertEqual(self.physical_file.read_bytes(), self.original_bytes)
        for obj in self.objects():
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())

    def test_superuser_and_staff_can_only_view_business_models(self):
        for user in (self.system, self.staff):
            self.client.force_login(user)
            for obj in self.objects():
                with self.subTest(user=user.email, model=type(obj).__name__):
                    response = self.client.get(self.url(obj, "change"))
                    self.assertEqual(response.status_code, 200)
                    form = response.context["adminform"]
                    self.assertFalse(response.context["has_change_permission"])
                    self.assertFalse(response.context["has_delete_permission"])
                    self.assertFalse(response.context["has_add_permission"])
                    self.assertFalse(form.form.fields)

    def test_crafted_order_author_change_is_denied_even_for_superuser(self):
        for user in (self.system, self.staff):
            self.client.force_login(user)
            response = self.client.post(self.url(self.order, "change"), {
                "created_by_user": self.director.pk, "_save": "Save",
            })
            self.assertEqual(response.status_code, 403)
            self.assert_history_intact()

    def test_completed_without_report_is_denied_even_for_superuser(self):
        for user in (self.system, self.staff):
            self.client.force_login(user)
            response = self.client.post(self.url(self.other_order, "change"), {
                "status": "COMPLETED", "_save": "Save",
            })
            self.assertEqual(response.status_code, 403)
            self.other_order.refresh_from_db()
            self.assertEqual(self.other_order.status, "NEW")
            self.assertFalse(File.objects.filter(order=self.other_order).exists())

    def test_business_add_change_and_single_delete_posts_are_denied(self):
        for user in (self.system, self.staff):
            self.client.force_login(user)
            for obj in self.objects():
                with self.subTest(user=user.email, model=type(obj).__name__):
                    for action in ("change", "delete"):
                        response = self.client.post(self.url(obj, action), {
                            "post": "yes", "_save": "Save", "file_path": "elsewhere.pdf",
                            "order": self.other_order.pk, "violation": self.violation.pk,
                        })
                        self.assertEqual(response.status_code, 403)
                    add_url = reverse(f"admin:prescriptions_{obj._meta.model_name}_add")
                    self.assertEqual(self.client.post(add_url, {}).status_code, 403)
            self.assert_history_intact()

    def test_bulk_delete_unavailable_and_crafted_action_preserves_history(self):
        for user in (self.system, self.staff):
            self.client.force_login(user)
            for obj in self.objects():
                url = reverse(f"admin:prescriptions_{obj._meta.model_name}_changelist")
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'value="delete_selected"')
                self.client.post(url, {
                    "action": "delete_selected", "_selected_action": [obj.pk], "post": "yes",
                })
            self.assert_history_intact()

    def test_application_admin_does_not_gain_system_admin_access(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url(self.order, "change")).status_code, 302)
        self.assertEqual(self.client.post(self.url(self.order, "delete"), {"post": "yes"}).status_code, 302)
        self.assert_history_intact()
