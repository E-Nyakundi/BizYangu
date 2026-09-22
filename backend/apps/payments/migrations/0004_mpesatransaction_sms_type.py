from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_businessmpesacredentials'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mpesatransaction',
            name='transaction_type',
            field=models.CharField(
                max_length=10,
                choices=[
                    ('C2B', 'Customer to Business'),
                    ('STK_PUSH', 'STK Push'),
                    ('B2C', 'Business to Customer'),
                    ('SMS', 'SMS Reconciliation'),
                ],
            ),
        ),
    ]
