# Generated by Django 2.0.9 on 2018-10-22 17:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0001_initial'),
        ('anchorimport', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='anchorimportagreements',
            name='agreementclosedflag',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.ncf_applicationwide_text', to_field='app_text_code'),
        ),
        migrations.AddField(
            model_name='anchorimportagreements',
            name='agreementcustomernumber',
            field=models.ForeignKey(blank=True, db_column='AgreementCustomerNumber', max_length=10, null=True, on_delete=django.db.models.deletion.CASCADE, to='anchorimport.AnchorimportCustomers', to_field='customernumber'),
        ),
        migrations.AddField(
            model_name='anchorimportagreement_querydetail',
            name='agreementagreementtypeid',
            field=models.ForeignKey(blank=True, db_column='AgreementAgreementTypeID', null=True, on_delete=django.db.models.deletion.CASCADE, to='anchorimport.AnchorimportAgreementDefinitions', to_field='agreementdefid'),
        ),
        migrations.AddField(
            model_name='anchorimportagreement_querydetail',
            name='agreementclosedflag',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.ncf_applicationwide_text', to_field='app_text_code'),
        ),
        migrations.AddField(
            model_name='anchorimportagreement_querydetail',
            name='agreementcustomernumber',
            field=models.ForeignKey(blank=True, db_column='AgreementCustomerNumber', max_length=10, null=True, on_delete=django.db.models.deletion.CASCADE, to='anchorimport.AnchorimportCustomers', to_field='customernumber'),
        ),
    ]
