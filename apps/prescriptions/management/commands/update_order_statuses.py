from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.prescriptions.deadlines import warning_end
from apps.prescriptions.models import Order


class Command(BaseCommand):
    help = "Обновить активные статусы: просрочка, 10 рабочих дней, начало исполнения."

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        end = warning_end(today)
        active = Order.objects.exclude(status="COMPLETED")
        groups = {
            "OVERDUE": active.filter(deadline_date__lt=today),
            "EXPIRING": active.filter(deadline_date__gte=today, deadline_date__lte=end),
            "IN_PROGRESS": active.filter(deadline_date__gt=end, issue_date__lt=today),
            "NEW": active.filter(deadline_date__gt=end, issue_date__gte=today),
        }
        total = 0
        for status, queryset in groups.items():
            count = queryset.exclude(status=status).update(status=status, updated_at=timezone.now())
            total += count
            self.stdout.write(f"{status}: {count}")
        self.stdout.write(self.style.SUCCESS(f"Изменено: {total}"))
