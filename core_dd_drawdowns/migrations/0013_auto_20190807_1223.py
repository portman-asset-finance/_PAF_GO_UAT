# Generated by Django 2.0.9 on 2019-08-07 12:23

from django.db import migrations

from core_dd_drawdowns.models import StatusDefinition


def populate_status_definition_table(apps, schema_editor):

    try:
        new_rec = StatusDefinition(text_code='ARCHIVED', text_description='ARCHIVED')
        new_rec.save()
    except:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('core_dd_drawdowns', '0012_auto_20190801_1212'),
    ]

    operations = [
        migrations.RunPython(populate_status_definition_table)
    ]
