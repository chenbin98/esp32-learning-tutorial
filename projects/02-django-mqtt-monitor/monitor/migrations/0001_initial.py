from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name='DeviceState', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('device_id', models.CharField(max_length=80, unique=True)),
            ('last_seen', models.DateTimeField(blank=True, null=True)),
            ('mode', models.CharField(default='auto', max_length=10)),
            ('led_on', models.BooleanField(default=False)),
            ('pending_command_id', models.CharField(blank=True, max_length=40)),
            ('pending_command_at', models.DateTimeField(blank=True, null=True)),
            ('last_command_result', models.CharField(blank=True, max_length=40)),
        ]),
        migrations.CreateModel(name='Reading', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('device_id', models.CharField(db_index=True, max_length=80)),
            ('received_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ('temperature', models.FloatField(blank=True, null=True)),
            ('humidity', models.FloatField(blank=True, null=True)),
            ('sensor_ok', models.BooleanField(default=False)),
            ('alarm_condition', models.BooleanField(default=False)),
            ('mode', models.CharField(default='auto', max_length=10)),
            ('led_on', models.BooleanField(default=False)),
            ('error', models.CharField(blank=True, max_length=200)),
        ], options={'ordering': ['-received_at']}),
    ]
