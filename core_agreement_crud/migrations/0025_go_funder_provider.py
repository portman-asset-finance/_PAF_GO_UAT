# Generated by Django 2.1.12 on 2019-09-16 10:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_agreement_crud', '0024_auto_20190910_1624'),
    ]

    operations = [
        migrations.AddField(
            model_name='go_funder',
            name='provider',
            field=models.CharField(blank=True, choices=[('datacash', 'datacash'), ('eazycollect', 'eazycollect')], max_length=50, null=True),
        ),
    ]