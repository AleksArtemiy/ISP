from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.institutions.models import Institution
from apps.test_support import Stage1DataMixin


class DashboardTests(Stage1DataMixin, TestCase):
    def test_queries_do_not_grow_with_institution_count(self):
        self.client.force_login(self.committee)
        with CaptureQueriesContext(connection) as first:
            self.assertEqual(self.client.get('/').status_code, 200)
        for n in range(22):
            Institution.objects.create(name=f'Школа {n}', short_name=f'S-{n}', address='Адрес', institution_type=self.inst.institution_type)
        with CaptureQueriesContext(connection) as second:
            self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(len(first), len(second))
        self.assertLessEqual(len(second), 8)

    def test_scoped_dashboard_access(self):
        self.client.force_login(self.director)
        self.assertEqual(self.client.get('/').status_code, 302)
        response = self.client.get(f'/institution/{self.inst.pk}/')
        self.assertContains(response, 'A-1')
        self.assertNotContains(response, 'B-1')
        self.assertEqual(self.client.get(f'/institution/{self.other_inst.pk}/').status_code, 302)
        for user in (self.unknown, self.unassigned):
            self.client.force_login(user)
            self.assertEqual(self.client.get('/').status_code, 403)
