# Generated by Django 2.0.9 on 2019-05-14 11:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_notes', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='asset',
            name='dir_name',
            field=models.CharField(max_length=250),
        ),
        migrations.AlterField(
            model_name='asset',
            name='file_name',
            field=models.CharField(max_length=250),
        ),
        migrations.AlterField(
            model_name='asset',
            name='file_type',
            field=models.CharField(max_length=50),
        ),
        migrations.AlterField(
            model_name='asset',
            name='original_file_name',
            field=models.CharField(max_length=250),
        ),
        migrations.AlterField(
            model_name='type',
            name='description',
            field=models.CharField(max_length=250),
        ),
    ]
