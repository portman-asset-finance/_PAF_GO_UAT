# Generated by Django 2.0.9 on 2019-06-13 13:27

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core_notes', '0016_auto_20190613_1341'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='contacts',
            name='user',
        ),
        migrations.AddField(
            model_name='contacts',
            name='last_updated_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL),
        ),
    ]