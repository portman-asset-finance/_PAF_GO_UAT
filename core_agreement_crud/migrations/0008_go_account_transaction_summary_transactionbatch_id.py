# Generated by Django 2.0.9 on 2019-06-05 09:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_agreement_crud', '0007_go_agreement_index_consolidation_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='go_account_transaction_summary',
            name='transactionbatch_id',
            field=models.CharField(db_column='TransactionBatch_id', default='', max_length=10, null=True),
        ),
    ]
