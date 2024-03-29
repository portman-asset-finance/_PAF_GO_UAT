# Generated by Django 2.1.12 on 2019-09-13 17:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_eazycollect', '0003_delete_requestlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='RequestLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('agreement_id', models.CharField(blank=True, max_length=50, null=True)),
                ('request_type', models.CharField(blank=True, choices=[('payment', 'payment'), ('customer', 'customer'), ('contract', 'contact')], max_length=50, null=True)),
                ('http_method', models.CharField(blank=True, choices=[('GET', 'GET'), ('PUT', 'PUT'), ('POST', 'POST'), ('PATCH', 'PATCH'), ('DELETE', 'DELETE')], max_length=10, null=True)),
                ('url', models.CharField(blank=True, max_length=250, null=True)),
                ('headers', models.TextField(blank=True, null=True)),
                ('request', models.TextField(blank=True, null=True)),
                ('response', models.TextField(blank=True, null=True)),
                ('created', models.DateTimeField()),
                ('updated', models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]
