from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from apps.test_support import Stage1DataMixin
from .models import File, Order, OrderViolation, Violation


class HistoryTests(Stage1DataMixin, TestCase):
    def test_delete_reference_preserves_orders(self):
        for obj in (self.inst, self.authority, self.committee):
            with self.subTest(model=type(obj).__name__):
                with self.assertRaises(ProtectedError):
                    obj.delete()
        self.assertEqual(Order.objects.count(), 2)

    def test_uploader_and_order_with_file_are_protected(self):
        File.objects.create(order=self.order, uploaded_by_user=self.director,
            original_filename="history.pdf", file_path="history.pdf")
        for obj in (self.director, self.order):
            with self.assertRaises(ProtectedError):
                obj.delete()

    def test_used_violation_is_protected(self):
        violation = Violation.objects.create(description="Нарушение")
        OrderViolation.objects.create(order=self.order, violation=violation)
        with self.assertRaises(ProtectedError):
            violation.delete()

    def test_admin_protected_delete_returns_understandable_error(self):
        self.client.force_login(self.system)
        response = self.client.post(reverse("admin_panel:admin_institution_delete", args=[self.inst.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 409)
        self.assertIn("историческими", response.json()["error"])
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    def test_user_action_deactivates_and_preserves_history(self):
        self.client.force_login(self.system)
        self.client.post(reverse("admin_panel:admin_user_delete", args=[self.committee.pk]))
        self.committee.refresh_from_db()
        self.assertFalse(self.committee.is_active)
        self.assertEqual(Order.objects.filter(created_by_user=self.committee).count(), 2)
