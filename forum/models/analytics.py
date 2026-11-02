"""First-party usage history; payloads never contain user-supplied content."""
import uuid

from django.db import models
from django.utils import timezone


class AnalyticsEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    # Deliberately not a foreign key: deleting an account must not rewrite counts
    # or prevent account deletion. Only the internal numeric identity is retained.
    account_id = models.PositiveBigIntegerField()
    platform = models.CharField(max_length=6, choices=[('web', 'Web'), ('mobile', 'Mobile')])
    event_type = models.CharField(max_length=24)
    screen = models.CharField(max_length=32)

    class Meta:
        default_permissions = ()
        permissions = [('export_analytics', 'Can export daily analytics')]
        indexes = [models.Index(fields=['event_type', 'occurred_at'], name='analytics_type_time_idx')]


class AnalyticsCoverage(models.Model):
    """Seeded on migration, so an empty tracked day differs from missing history."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    started_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
