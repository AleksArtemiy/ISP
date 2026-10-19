from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.test_support import Stage1DataMixin
from .deadlines import effective_status, warning_end, working_days_between
from .models import Order


class CalendarTests(SimpleTestCase):
    def test_friday_weekends_and_9_10_11_days(self):
        today = date(2026, 10, 16)  # Friday
        self.assertEqual(working_days_between(today, date(2026, 10, 29)), 9)
        self.assertEqual(working_days_between(today, date(2026, 10, 30)), 10)
        self.assertEqual(working_days_between(today, date(2026, 11, 2)), 11)
        self.assertEqual(warning_end(today), date(2026, 11, 1))
        self.assertEqual(working_days_between(today, today+timedelta(days=2)), 0)
        self.assertEqual(warning_end(today+timedelta(days=1)), date(2026, 11, 1))


class StatusTests(Stage1DataMixin, TestCase):
    def test_deadline_today_boundary_overdue_and_completed(self):
        today = date(2026, 10, 16)
        for deadline, expected in ((date(2026, 10, 15), 'OVERDUE'), (today, 'EXPIRING'),
                                   (date(2026, 10, 29), 'EXPIRING'), (date(2026, 10, 30), 'EXPIRING'),
                                   (date(2026, 11, 2), 'IN_PROGRESS')):
            self.order.issue_date = date(2026, 1, 1)
            self.order.deadline_date = deadline
            self.assertEqual(effective_status(self.order, today), expected)
        self.order.status = 'COMPLETED'
        self.order.deadline_date = date(2026, 1, 1)
        self.assertEqual(effective_status(self.order, today), 'COMPLETED')

    def test_command_updates_and_second_run_is_noop(self):
        today = date(2026, 10, 16)
        Order.objects.filter(pk=self.order.pk).update(issue_date=date(2026, 1, 1), deadline_date=today)
        Order.objects.filter(pk=self.other_order.pk).update(status='COMPLETED', deadline_date=date(2026, 1, 1))
        with patch('apps.prescriptions.management.commands.update_order_statuses.timezone.localdate', return_value=today):
            call_command('update_order_statuses', stdout=StringIO())
            output = StringIO()
            call_command('update_order_statuses', stdout=output)
        self.order.refresh_from_db()
        self.other_order.refresh_from_db()
        self.assertEqual(self.order.status, 'EXPIRING')
        self.assertEqual(self.other_order.status, 'COMPLETED')
        self.assertIn('Изменено: 0', output.getvalue())
