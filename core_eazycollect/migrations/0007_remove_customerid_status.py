# Generated by Django 2.1.12 on 2019-09-16 12:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core_eazycollect', '0006_customerid'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='customerid',
            name='status',
        ),
    ]