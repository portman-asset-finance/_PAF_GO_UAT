# Generated by Django 2.0.9 on 2019-07-18 14:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_agreement_crud', '0017_auto_20190717_1154'),
    ]

    operations = [
        migrations.AddField(
            model_name='go_agreement_index',
            name='consolidated_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='go_agreement_index',
            name='globalled_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='go_agreement_index',
            name='settled_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
