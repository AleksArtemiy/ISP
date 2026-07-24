from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.prescriptions.models import Order

class Command(BaseCommand):
    help = 'Автоматически обновляет статусы предписаний: NEW→IN_PROGRESS (через 1 день), EXPIRING (за 14 дней до дедлайна), OVERDUE (после дедлайна)'

    def handle(self, *args, **options):
        today = timezone.now().date()

        # 1. Все, у кого дедлайн меньше сегодня → OVERDUE (кроме уже COMPLETED)
        overdue_orders = Order.objects.filter(
            status__in=['NEW', 'IN_PROGRESS', 'EXPIRING'],
            deadline_date__lt=today
        )
        count_overdue = overdue_orders.update(status='OVERDUE')
        self.stdout.write(self.style.SUCCESS(f'Просроченных предписаний переведено в OVERDUE: {count_overdue}'))

        # 2. Все, у кого дедлайн <= today + 14 дней и не OVERDUE/COMPLETED → EXPIRING
        expiring_date = today + timedelta(days=14)
        expiring_orders = Order.objects.filter(
            status__in=['NEW', 'IN_PROGRESS'],
            deadline_date__lte=expiring_date,
            deadline_date__gte=today  # не просрочены (уже обработаны на шаге 1)
        )
        count_expiring = expiring_orders.update(status='EXPIRING')
        self.stdout.write(self.style.SUCCESS(f'Предписаний переведено в EXPIRING: {count_expiring}'))

        # 3. NEW → IN_PROGRESS (через 1 день после выдачи) только если дедлайн > 14 дней
        one_day_ago = today - timedelta(days=1)
        in_progress_orders = Order.objects.filter(
            status='NEW',
            issue_date__lte=one_day_ago,
            deadline_date__gt=expiring_date  # дедлайн > today + 14
        )
        count_in_progress = in_progress_orders.update(status='IN_PROGRESS')
        self.stdout.write(self.style.SUCCESS(f'Предписаний переведено из NEW в IN_PROGRESS: {count_in_progress}'))