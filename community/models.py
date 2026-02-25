from django.db import models
from django.utils import timezone
import uuid


class Community(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    population = models.PositiveIntegerField()
    tier = models.CharField(max_length=50)
    region = models.CharField(max_length=50)
    zone = models.CharField(max_length=50)
    province = models.CharField(max_length=50)
    year = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True, db_index=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # now = timezone.now()

        # # Force inactive if the end date has passed
        # if self.end_date and self.end_date < now:
        #     self.is_active = False

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
