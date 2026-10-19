from django.core.management.base import BaseCommand

from apps.accounts.throttling import cleanup_expired_counters


class Command(BaseCommand):
    help = "Delete expired login counters in short batches; run every five minutes."

    def handle(self, *args, **options):
        total = 0
        while deleted := cleanup_expired_counters():
            total += deleted
        self.stdout.write(f"Deleted expired login counters: {total}")
