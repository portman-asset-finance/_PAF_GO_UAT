# Generated by Django 2.0.9 on 2019-05-30 15:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_notes', '0006_type_selectable'),
    ]

    operations = [
        migrations.AddField(
            model_name='type',
            name='level',
            field=models.CharField(choices=[('Normal', 'Normal'), ('Customer', 'Customer'), ('Agreement', 'Agreement')], max_length=20, null=True),
        ),
    ]
