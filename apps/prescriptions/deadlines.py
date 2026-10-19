"""One business calendar for commands, dashboards and deadline warnings.

Count (today, deadline], excluding today. Holidays may be supplied by a
WORKDAY_CALENDAR callable import path; the default is Monday through Friday.
"""
from datetime import timedelta

from django.conf import settings
from django.utils.module_loading import import_string


def is_workday(day):
    calendar = getattr(settings, "WORKDAY_CALENDAR", "")
    return import_string(calendar)(day) if calendar else day.weekday() < 5


def working_days_between(start, end):
    if end < start:
        return -working_days_between(end, start)
    count = 0
    while start < end:
        start += timedelta(days=1)
        count += bool(is_workday(start))
    return count


def warning_end(today, days=10):
    result, remaining = today, days
    while remaining:
        result += timedelta(days=1)
        remaining -= bool(is_workday(result))
    # A weekend deadline still has only ten working days before it.
    while not is_workday(result + timedelta(days=1)):
        result += timedelta(days=1)
    return result


def effective_status(order, today):
    if order.status == "COMPLETED":
        return "COMPLETED"
    if order.deadline_date < today:
        return "OVERDUE"
    if order.deadline_date <= warning_end(today):
        return "EXPIRING"
    return "IN_PROGRESS" if order.issue_date < today else "NEW"


def deadline_display(order, today):
    status = effective_status(order, today)
    days = (order.deadline_date - today).days
    if status == "COMPLETED":
        color, progress, text = "green", 100, "Выполнено"
    elif status == "OVERDUE":
        color, progress, text = "red", 0, f"Просрочено на {-days} календ. дн."
    elif status == "EXPIRING":
        color, progress = "yellow", 50
        text = f"До срока: {working_days_between(today, order.deadline_date)} раб. дн. ({days} календ.)"
    else:
        color, progress, text = "green", 75, f"До окончания: {days} календ. дн."
    return {"status": status, "status_class": color, "progress_percent": progress, "status_text": text}
