# Generated by Django 2.0.9 on 2019-06-04 13:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_notes', '0009_auto_20190604_1040'),
    ]

    operations = [
        migrations.AddField(
            model_name='asset',
            name='follow_up',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
