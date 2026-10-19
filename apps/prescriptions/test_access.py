import tempfile
from pathlib import Path
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.test_support import Stage1DataMixin
from .models import File, Order, OrderViolation, Violation
from .test_files import pdf_upload


class PrescriptionAccessTests(Stage1DataMixin, TestCase):
    def payload(self, **extra):
        value = {'number': 'CREATED', 'institution': self.other_inst.pk, 'authority': self.authority.pk,
                 'created_by_user': self.admin.pk, 'status': 'COMPLETED', 'issue_date': '2026-01-01',
                 'deadline_date': '2026-12-01', 'violations-TOTAL_FORMS': 1,
                 'violations-INITIAL_FORMS': 0, 'violations-0-text': 'Violation'}
        value.update(extra)
        return value

    def test_read_and_write_matrix(self):
        for user, allowed in ((self.admin, True), (self.system, True), (self.committee, True),
                              (self.director, True), (self.unknown, False), (self.unassigned, False)):
            self.client.force_login(user)
            for path in ('/prescriptions/', '/prescriptions/create/', f'/prescriptions/{self.order.pk}/',
                         f'/prescriptions/update/{self.order.pk}/', f'/prescriptions/complete/{self.order.pk}/'):
                self.assertEqual(self.client.get(path).status_code, 200 if allowed else 403)
        self.client.logout()
        self.assertEqual(self.client.get('/prescriptions/').status_code, 302)

    def test_director_cannot_access_other_order_even_by_post(self):
        self.client.force_login(self.director)
        for path in (f'/prescriptions/{self.other_order.pk}/', f'/prescriptions/update/{self.other_order.pk}/'):
            self.assertEqual(self.client.get(path).status_code, 404)
            self.assertEqual(self.client.post(path, self.payload()).status_code, 404 if '/update/' in path else 405)
        self.assertEqual(self.client.post(f'/prescriptions/complete/{self.other_order.pk}/', {'report': pdf_upload()}).status_code, 403)

    def test_post_tampering_on_create_and_update(self):
        self.client.force_login(self.director)
        response = self.client.post('/prescriptions/create/?institution=' + str(self.other_inst.pk), self.payload())
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(number='CREATED')
        self.assertEqual((order.institution_id, order.created_by_user_id, order.status), (self.inst.pk, self.director.pk, 'NEW'))
        self.assertEqual(self.client.post(f'/prescriptions/update/{self.order.pk}/', self.payload(number=self.order.number)).status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual((self.order.institution_id, self.order.created_by_user_id, self.order.status), (self.inst.pk, self.committee.pk, 'NEW'))

    def test_creator_immutable_for_committee(self):
        self.client.force_login(self.admin)
        response = self.client.post(f'/prescriptions/update/{self.order.pk}/', self.payload(number=self.order.number, status='NEW'))
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.created_by_user_id, self.committee.pk)

    def test_complete_requires_saved_valid_report_and_is_atomic(self):
        self.client.force_login(self.director)
        path = f'/prescriptions/complete/{self.order.pk}/'
        self.assertEqual(self.client.post(path).status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'NEW')
        with tempfile.TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            with patch.object(Order, 'save', side_effect=IntegrityError('injected')):
                with self.assertRaises(IntegrityError):
                    self.client.post(path, {'report': pdf_upload()})
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, 'NEW')
            self.assertEqual(File.objects.count(), 0)
            self.assertEqual(list(Path(folder).rglob('*.pdf')), [])
            self.assertEqual(self.client.post(path, {'report': pdf_upload()}).status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'COMPLETED')
        self.assertEqual(self.order.files.count(), 1)

    def test_create_database_failure_leaves_no_partial_order_or_violation(self):
        self.client.force_login(self.committee)
        before = (Order.objects.count(), Violation.objects.count(), OrderViolation.objects.count())
        with patch('apps.prescriptions.views.OrderViolation.objects.create', side_effect=IntegrityError('injected')):
            with self.assertRaises(IntegrityError):
                self.client.post('/prescriptions/create/', self.payload(status='NEW'))
        self.assertEqual((Order.objects.count(), Violation.objects.count(), OrderViolation.objects.count()), before)


class FilterTests(Stage1DataMixin, TestCase):
    def test_combined_filters_and_invalid_values_fail_closed(self):
        self.client.force_login(self.committee)
        response = self.client.get('/prescriptions/', {'q': 'A-', 'status': 'NEW', 'authority': self.authority.pk,
            'institution': self.inst.pk, 'deadline_from': '2000-01-01', 'deadline_to': '2099-01-01'})
        self.assertEqual(list(response.context['orders']), [self.order])
        for params in ({'authority': 'abc'}, {'institution': '-1'}, {'status': 'bad'},
                       {'deadline_from': 'garbage'}, {'issue_from': '2026-12-01', 'issue_to': '2026-01-01'}):
            self.assertEqual(list(self.client.get('/prescriptions/', params).context['orders']), [])

    def test_director_filter_never_expands_scope(self):
        self.client.force_login(self.director)
        for institution in ('', str(self.other_inst.pk), 'invalid'):
            response = self.client.get('/prescriptions/', {'institution': institution})
            self.assertNotIn(self.other_order, list(response.context['orders']))

    def test_pagination_preserves_encoded_filters(self):
        self.client.force_login(self.committee)
        for n in range(25):
            Order.objects.create(number=f'A&{n}', institution=self.inst, authority=self.authority,
                created_by_user=self.committee, issue_date=self.order.issue_date, deadline_date=self.order.deadline_date)
        response = self.client.get('/prescriptions/', {'q': 'A&', 'authority': self.authority.pk})
        self.assertEqual(len(response.context['orders']), 20)
        self.assertContains(response, 'q=A%26')
        self.assertContains(response, 'page=2')
