# Generated by Django 2.1.12 on 2019-09-18 14:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_eazycollect', '0015_auto_20190918_1438'),
    ]

    operations = [
        migrations.AddField(
            model_name='payments',
            name='error',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='payments',
            name='message',
            field=models.TextField(blank=True, null=True),
        ),
    ]
