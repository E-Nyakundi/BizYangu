from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExternalSource',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('domain', models.CharField(db_index=True, max_length=255, unique=True)),
                ('kind', models.CharField(
                    choices=[
                        ('AGGREGATOR', 'Aggregator (barcode-list.com-style)'),
                        ('RETAILER', "Retailer's own product page"),
                        ('OTHER', 'Other'),
                    ],
                    default='OTHER', max_length=12,
                )),
                ('hits_confirmed', models.PositiveIntegerField(default=0)),
                ('hits_disputed', models.PositiveIntegerField(default=0)),
                ('candidates_contributed', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-hits_confirmed'],
            },
        ),
        migrations.AddField(
            model_name='globalproduct',
            name='web_sources',
            field=models.ManyToManyField(blank=True, related_name='candidates', to='products.externalsource'),
        ),
    ]
