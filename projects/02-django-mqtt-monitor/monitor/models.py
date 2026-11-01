from django.db import models


class Reading(models.Model):
    device_id = models.CharField(max_length=80, db_index=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)
    temperature = models.FloatField(null=True, blank=True)
    humidity = models.FloatField(null=True, blank=True)
    sensor_ok = models.BooleanField(default=False)
    alarm_condition = models.BooleanField(default=False)
    mode = models.CharField(max_length=10, default='auto')
    led_on = models.BooleanField(default=False)
    error = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-received_at']


class DeviceState(models.Model):
    device_id = models.CharField(max_length=80, unique=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(max_length=10, default='auto')
    led_on = models.BooleanField(default=False)
    pending_command_id = models.CharField(max_length=40, blank=True)
    pending_command_at = models.DateTimeField(null=True, blank=True)
    last_command_result = models.CharField(max_length=40, blank=True)
