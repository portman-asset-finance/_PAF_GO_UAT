# Generated by Django 2.0.9 on 2019-05-15 10:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_notes', '0002_auto_20190514_1224'),
    ]

    operations = [
        migrations.AlterField(
            model_name='asset',
            name='file_type',
            field=models.CharField(max_length=250),
        ),
    ]