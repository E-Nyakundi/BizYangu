from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_user_email_user_first_name_user_last_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(max_length=20, unique=True, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='user',
            name='google_sub',
            field=models.CharField(max_length=64, unique=True, null=True, blank=True),
        ),
    ]
