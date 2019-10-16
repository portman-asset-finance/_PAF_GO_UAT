# Generated by Django 2.0.9 on 2019-06-25 15:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_sage_export', '0007_remove_sagebatchheaders_datacash_batch_ref'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='sagebatchheaders',
            name='created',
        ),
        migrations.RemoveField(
            model_name='sagebatchheaders',
            name='updated',
        ),
        migrations.AlterField(
            model_name='sagebatchheaders',
            name='total_credit_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AlterField(
            model_name='sagebatchheaders',
            name='total_debit_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True),
        ),
    ]