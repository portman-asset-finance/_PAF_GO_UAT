# Generated by Django 2.0.9 on 2019-07-10 15:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_notes', '0019_auto_20190620_1017'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contacts',
            name='contact_mobile_number',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='contacts',
            name='contact_phone_number',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]