# Generated for BizYangu — Phase 3 (low-stock push notifications)

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('business', '0001_initial'),
        ('catalog', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceToken',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token', models.CharField(max_length=255, unique=True)),
                ('platform', models.CharField(choices=[('ANDROID', 'Android'), ('IOS', 'iOS'), ('WEB', 'Web')], default='ANDROID', max_length=10)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(auto_now=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_tokens', to='business.business')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_tokens', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('kind', models.CharField(choices=[('LOW_STOCK', 'Low Stock'), ('OUT_OF_STOCK', 'Out of Stock'), ('OTHER', 'Other')], default='OTHER', max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('body', models.CharField(max_length=500)),
                ('recipients_count', models.PositiveIntegerField(default=0)),
                ('sent_successfully', models.BooleanField(default=False)),
                ('error', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_logs', to='business.business')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='notification_logs', to='catalog.product')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
