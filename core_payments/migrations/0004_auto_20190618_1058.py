# Generated by Django 2.0.9 on 2019-06-18 09:58

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core_payments', '0003_auto_20190618_1031'),
    ]

    operations = [
        migrations.AlterField(
            model_name='receipt_record',
            name='rr_receipt_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core_payments.receipt_type', to_field='rt_type_code'),
        ),
    ]
