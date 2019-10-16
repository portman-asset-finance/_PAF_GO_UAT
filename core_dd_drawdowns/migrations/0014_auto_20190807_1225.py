# Generated by Django 2.0.9 on 2019-08-07 12:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_dd_drawdowns', '0013_auto_20190807_1223'),
    ]

    operations = [
        migrations.AlterField(
            model_name='statusdefinition',
            name='text_code',
            field=models.CharField(choices=[('OPEN', 'OPEN'), ('PROCESSING', 'PROCESSING'), ('SENT', 'SENT'), ('RECEIVED', 'RECEIVED'), ('REMOVED', 'REMOVED'), ('ARCHIVED', 'ARCHIVED')], db_column='text_code', max_length=20, unique=True),
        ),
    ]