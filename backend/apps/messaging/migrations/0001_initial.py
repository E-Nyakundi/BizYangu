import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='SMSDeliveryLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('phone_number', models.CharField(max_length=20)),
                ('provider_name', models.CharField(max_length=50)),
                ('success', models.BooleanField()),
                ('provider_message_id', models.CharField(blank=True, max_length=255)),
                ('error', models.TextField(blank=True)),
                ('purpose', models.CharField(default='otp', max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='smsdeliverylog',
            index=models.Index(fields=['provider_name', 'created_at'], name='messaging_s_provide_9c1a4e_idx'),
        ),
        migrations.AddIndex(
            model_name='smsdeliverylog',
            index=models.Index(fields=['phone_number', 'created_at'], name='messaging_s_phone_n_6f2b3d_idx'),
        ),
    ]
