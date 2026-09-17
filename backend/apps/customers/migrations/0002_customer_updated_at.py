# Phase 5 (offline sync) — Customer needs updated_at because it's a
# genuinely mutable record (name/phone/notes/is_active can all be edited
# after creation), unlike CustomerPayment which is append-only. A
# pull-sync keyed on "changed since timestamp X" needs this to notice an
# edited customer, not just a newly-created one.

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
