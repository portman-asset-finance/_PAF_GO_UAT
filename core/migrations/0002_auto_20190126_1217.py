# Generated by Django 2.0.9 on 2019-01-26 12:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ncf_bacs_ddic_reasons',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ddic_reason_code', models.CharField(max_length=1, unique=True)),
                ('ddic_reason_description', models.CharField(max_length=100)),
            ],
            options={
                'verbose_name_plural': '< 1.02 BACS DDIC Reason Codes',
                'ordering': ('ddic_reason_code',),
                'verbose_name': 'DDIC Reason Code',
            },
        ),
        migrations.CreateModel(
            name='ncf_dd_status_text',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dd_text_code', models.CharField(blank=True, max_length=1, null=True, unique=True)),
                ('dd_text_set', models.IntegerField(blank=True, null=True)),
                ('dd_text_description', models.CharField(blank=True, max_length=200, null=True)),
            ],
            options={
                'verbose_name_plural': 'DD Status Text Items',
                'ordering': ('dd_text_description',),
                'verbose_name': 'DD Status Text Item',
            },
        ),
        migrations.CreateModel(
            name='ncf_ddic_advices',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('agreement_id', models.CharField(blank=True, max_length=50, null=True)),
                ('ddic_SUReference', models.CharField(blank=True, max_length=50, null=True)),
                ('ddic_DDIC_Type', models.CharField(blank=True, max_length=50, null=True)),
                ('ddic_seqno', models.CharField(blank=True, max_length=50, null=True)),
                ('ddic_TotalDocumentValue', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('ddic_DateOfDocumentDebit', models.DateField(blank=True, null=True)),
                ('ddic_PayingBankReference', models.CharField(blank=True, max_length=250, null=True)),
                ('ddic_PayerSortCode', models.CharField(blank=True, max_length=50, null=True)),
                ('ddic_PayerName', models.CharField(blank=True, max_length=250, null=True)),
                ('ddic_PayerAccount', models.CharField(blank=True, max_length=50, null=True)),
                ('ddic_TotalAmount', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('ddic_DateOfOriginalDD', models.DateField(blank=True, null=True)),
                ('ddic_OriginalDDAmount', models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True)),
                ('file_name', models.CharField(blank=True, max_length=500, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('ddic_Reason', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.ncf_bacs_ddic_reasons')),
            ],
            options={
                'verbose_name_plural': '< 1.06 BACS DDIC Advices',
                'ordering': ('agreement_id',),
                'verbose_name': 'BACS DDIC Advice',
            },
        ),
        migrations.DeleteModel(
            name='ncf_sentinel_dd_batches',
        ),
        migrations.AlterModelOptions(
            name='ncf_auddis_addacs_advices',
            options={'ordering': ('dd_reference',), 'verbose_name': 'Auddis/Addacs Advice', 'verbose_name_plural': '< 1.04 BACS AUDDIS/ADDACS Advices'},
        ),
        migrations.AlterModelOptions(
            name='ncf_bacs_files_processed',
            options={'ordering': ('file_name',), 'verbose_name': 'BACS File Processed', 'verbose_name_plural': '< 1.03 BACS Files Processed'},
        ),
        migrations.AlterModelOptions(
            name='ncf_dd_audit_log',
            options={'ordering': ('da_agreement_id',), 'verbose_name': 'DD Audit Log Item', 'verbose_name_plural': '< 1.07 BACS DD Audit Log Items'},
        ),
        migrations.AlterModelOptions(
            name='ncf_udd_advices',
            options={'ordering': ('dd_reference',), 'verbose_name': 'UDD Advice', 'verbose_name_plural': '< 1.05 BACS UDD Advices'},
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_currency',
            field=models.CharField(blank=True, max_length=5, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_datacash_bacs_reason',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_datacash_batch_status',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_datacash_method',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_datacash_response',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_datacash_setup_no',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_datacash_stage',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_ddic_debit_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_ddic_seqno',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_ddic_value',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_document_value',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_due_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_new_account_name',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_original_process_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_original_value',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_payingbank_reference',
            field=models.CharField(blank=True, max_length=250, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_reason_type',
            field=models.CharField(blank=True, max_length=1, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_referencestrip',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_return_description',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_seqno',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_sourcetype',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_transcode',
            field=models.CharField(blank=True, max_length=2, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_audit_log',
            name='da_type',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_call_arrears',
            name='ar_agent_name',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_call_arrears',
            name='ar_created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_call_rejections',
            name='ar_agent_name',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='ncf_dd_call_rejections',
            name='ar_created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='ncf_udd_advices',
            name='dd_payer_account_number',
            field=models.CharField(blank=True, max_length=8, null=True),
        ),
        migrations.AddField(
            model_name='ncf_udd_advices',
            name='dd_payer_sort_code',
            field=models.CharField(blank=True, max_length=8, null=True),
        ),
        migrations.AlterField(
            model_name='ncf_dd_audit_log',
            name='da_account_name',
            field=models.CharField(blank=True, max_length=500, null=True),
        ),
        migrations.AlterField(
            model_name='ncf_dd_audit_log',
            name='da_payer_account_number',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
        migrations.AlterField(
            model_name='ncf_dd_audit_log',
            name='da_payer_new_account_number',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
        migrations.AlterField(
            model_name='ncf_dd_audit_log',
            name='da_payer_new_sort_code',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
        migrations.AlterField(
            model_name='ncf_dd_audit_log',
            name='da_payer_sort_code',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
        migrations.AlterField(
            model_name='ncf_dd_audit_log',
            name='da_reference',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='ncf_dd_audit_log',
            name='da_source',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='ncf_dd_call_arrears',
            name='ar_term',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AlterField(
            model_name='ncf_dd_call_rejections',
            name='ar_term',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
