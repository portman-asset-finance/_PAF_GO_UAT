# Generated by Django 2.0.9 on 2019-06-26 11:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_sage_export', '0018_auto_20190626_1223'),
    ]

    operations = [
        migrations.AddField(
            model_name='sagedependencytable',
            name='sage_batch_type',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]