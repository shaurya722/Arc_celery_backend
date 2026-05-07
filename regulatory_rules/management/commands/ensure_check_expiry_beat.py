"""
Install/update django-celery-beat PeriodicTask for regulatory_rules.tasks.check_expiry.

CELERY_BEAT_SCHEDULER=django_celery_beat.schedulers:DatabaseScheduler reads schedules from
the database only - nothing runs until a PeriodicTask row exists. Run this once per environment:

    python manage.py ensure_check_expiry_beat

Requires Celery worker + beat processes running (beat schedules, worker executes).
"""

from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


TASK = 'regulatory_rules.tasks.check_expiry'
DEFAULT_NAME = 'check-expiry (sites & rules expiry)'


class Command(BaseCommand):
    help = (
        'Creates or updates django-celery-beat PeriodicTask for check_expiry '
        '(required when using DatabaseScheduler).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Run interval in days (default: 1).',
        )
        parser.add_argument(
            '--disable',
            action='store_true',
            help='Disable the periodic task instead of enabling it.',
        )

    def handle(self, *args, **options):
        every = max(1, int(options['days']))
        interval, _ = IntervalSchedule.objects.get_or_create(every=every, period=IntervalSchedule.DAYS)

        duplicate_count, _ = PeriodicTask.objects.filter(task=TASK).exclude(name=DEFAULT_NAME).delete()

        task, created = PeriodicTask.objects.get_or_create(
            name=DEFAULT_NAME,
            defaults={
                'task': TASK,
                'interval': interval,
                'enabled': not options['disable'],
            },
        )
        if not created:
            task.task = TASK
            task.interval = interval
            task.crontab = None
            task.solar = None
            task.clocked = None
            task.enabled = not options['disable']
            task.save()

        action = 'Created' if created else 'Updated'
        state = 'enabled' if task.enabled else 'disabled'
        duplicate_msg = f' Removed {duplicate_count} duplicate task(s).' if duplicate_count else ''
        self.stdout.write(
            self.style.SUCCESS(
                f'{action} PeriodicTask "{task.name}" -> {TASK} every {every} day(s) ({state}).'
                f'{duplicate_msg} '
                'Ensure celery worker and beat are running.'
            )
        )
