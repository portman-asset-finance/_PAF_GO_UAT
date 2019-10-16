
from dateutil.relativedelta import *
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import re
import io
import pytz
import uuid
import json
import numpy
import decimal
import datetime
import traceback
from numpy import pmt

wip_utc = pytz.UTC

from django.db.models import Sum, Q

from decimal import Decimal

from django.urls import reverse
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from .models import go_customers, go_agreement_querydetail, go_agreements, go_broker, go_account_transaction_detail, go_account_transaction_summary, \
                    go_agreement_definitions, go_profile_types, go_agreement_index, go_sales_authority, transition_log, go_funder

from core_agreement_editor.models import go_editor_history

from core.models import ncf_applicationwide_text, \
                        go_extensions, \
                        ncf_dd_schedule, \
                        ncf_datacash_drawdowns, \
                        ncf_dd_audit_log, \
                        ncf_regulated_agreements

from core_direct_debits.models import DDHistory

from .functions import validate_agreement_number, validate_tab1, generate_customer_number, validate_date, get_holidays, get_next_due_date, consolidation_function, archive_agreement_function, unarchive_agreement_function, refund_function

from core_direct_debits.functions import generate_dd_reference, update_ddi_status, cancel_ddi_with_datacash

from .filters import agreement_querydetail_Filter, \
                     accounttransactionsummary_Filter, \
                     ncf_arrears_summary_Filter, ncf_ddic_advices_Filter, customers_Filter, go_editor_history_Filter

from core_direct_debits.functions import generate_dd_reference, create_ddi_with_datacash, create_ddi_with_eazycollect

from core.functions_go_id_selector import requiredtabs, client_configuration, riskfeenetamount, daysbeforecalldd, daysbeforeddsetup,  pmt_commission, pmt_yield

from core_agreement_crud.functions import recalculate_function, reopen_function

from core_dd_drawdowns.models import DrawDown, StatusDefinition

import datetime
from datetime import timedelta


@login_required(login_url='signin')
def auto_complete(request):
    """
    Searches the customer table with values that contains a given search string.
    :return:
    """

    search_value = request.GET['search_value']

    context = {
        'data': []
    }

    if len(search_value) > 2:
        for row in go_customers.objects.filter(customercompany__contains=search_value)[:10]:
            context['data'].append('{} ({})'.format(row.customercompany, row.customernumber))

    return JsonResponse(context)


@login_required(login_url='signin')
def get_customer(request, customer_number):

    data = {}

    fields = ('customercompany', 'customername', 'customercontact', 'customeraddress1', 'customeraddress2',
              'customeraddress3', 'customeraddress4', 'customeraddress5', 'customerpostcode', 'customeremail',
              'customermobilenumber', 'customerphonenumber', 'customernumber', 'customerfirstname', 'customersurname')

    customer_rec = go_customers.objects.get(customernumber=customer_number)

    for k in fields:
        data[k] = getattr(customer_rec, k)

    return JsonResponse({'data': data})


@login_required(login_url="signin")
def AgreementEnquiryList(request):

    agreement_extract = go_agreement_querydetail.objects.filter()
    if not request.GET.get('agreement_closed_reason'):
        agreement_extract = agreement_extract.exclude(agreement_closed_reason='Archived')
    agreement_list = agreement_querydetail_Filter(request.GET, queryset=agreement_extract)
    paginator = Paginator(agreement_list.qs, 10)
    page = request.GET.get('page')
    try:
        pub = paginator.page(page)
    except PageNotAnInteger:
        pub = paginator.page(1)
    except EmptyPage:
        pub = paginator.page(paginator.num_pages)
    has_filter = request.GET.get('agreementnumber') or request.GET.get('customercompany') \
                 or request.GET.get('agreementclosedflag_id') or request.GET.get('agreementddstatus_id') \
                 or request.GET.get('agreement_status')

    request.session['arrears_by_arrears_return_querystring'] = {}
    request.session['arrears_by_arrears_return_querystring'] = request.get_full_path()

    return render(request, 'core_agreement_crud/agreement_management.html', {'agreement_list': agreement_list,
                                                           'agreement_list_qs': pub,
                                                           'requiredtabs': str(requiredtabs()),
                                                           'has_filter': has_filter,
                                                           'agreement_closed_reason': request.GET.get('agreement_closed_reason')
                                                           })


def active(request):
    return JsonResponse({
        'count': go_agreement_querydetail.objects.filter(agreement_stage='3').count()
    })


@login_required(login_url="signin")
def scapegoat(request):
    # agreement_extract = go_agreement_querydetail.objects.all()
    # agreement_list = agreement_querydetail_Filter(request.GET, queryset=agreement_extract)

    scapegoat_extract = go_editor_history.objects.all()
    scapegoat_list = go_editor_history_Filter(request.GET, queryset=scapegoat_extract)

    paginator = Paginator(scapegoat_list.qs, 10)
    page = request.GET.get('page')
    try:
        pub = paginator.page(page)
    except PageNotAnInteger:
        pub = paginator.page(1)
    except EmptyPage:
        pub = paginator.page(paginator.num_pages)
    has_filter = request.GET.get('agreement_id') \
                or request.GET.get('user_id') or request.GET.get('action') \
                or request.GET.get('updated')
                # or request.GET.get('customercompany') \

    return render(request, 'core_agreement_crud/scapegoat.html', {'scapegoat_list': scapegoat_list,
                                                                  'scapegoat_list_qs': pub,
                                                                  'requiredtabs': str(requiredtabs()),
                                                                  'has_filter': has_filter
                                                                  })


@login_required(login_url="signin")
def AgreementManagementDetail(request, agreement_id):

    # Core Querysets
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    agreement_customer = go_customers.objects.get(customernumber=agreement_detail.agreementcustomernumber)
    account_detail = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id)\
                        .order_by('transtypedesc',)
    config = client_configuration.objects.get(client_id="NWCF")
    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    account_summary = go_account_transaction_summary.objects.filter(agreementnumber=agreement_id)

    account_detail_fees = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                                              transactionsourceid='GO1',
                                                                              transtypeid__isnull=False) \
                                                                                .order_by('transtypedesc', )
    bacs_audit = ncf_dd_audit_log.objects.filter(da_agreement_id=agreement_id)\
                                            .order_by('-da_effective_date', 'da_source')

    # Get Regulated Status
    agreement_regulated = ncf_regulated_agreements.objects.filter(ra_agreement_id=agreement_id).exists()
    if agreement_regulated:
        agreement_regulated_flag = True
    else:
        agreement_regulated_flag = False

    # Agreement Type
    if agreement_detail.agreementdefname != 'Hire Purchase' and agreement_detail.agreementdefname != 'Management Fee':
        agreement_type = 'Lease'
        sales_tax_rate = config.other_sales_tax
    else:
        agreement_type = 'HP'
        sales_tax_rate = 1.0

    # Agreement Payable Net of VAT
    try:
        agreement_payable_net = agreement_detail.agreementoriginalprincipal + agreement_detail.agreementcharges
    except:
        agreement_payable_net = 0

    # Add in Fees if they exist
    try:
        agreement_fees_net = account_detail_fees.aggregate(Sum('transnetpayment'))
        if agreement_fees_net is not None:
            agreement_payable_net += agreement_fees_net["transnetpayment__sum"]
    except:
        agreement_fees_net = None
        agreement_payable_net = 0

    # Agreement Payable Gross of VAT
    agreement_payable_gross = (agreement_payable_net * decimal.Decimal(sales_tax_rate))

    # Agreement Instalment Gross
    agreement_instalment_gross = agreement_detail.agreementinstalmentnet
    if agreement_detail.agreementinstalmentvat  is not None:
        agreement_instalment_gross += agreement_detail.agreementinstalmentvat
    if agreement_detail.agreementinstalmentins is not None:
        agreement_instalment_gross += agreement_detail.agreementinstalmentins

        # Sundry Items
    settlement_figure_queryset = account_summary.aggregate(Sum('transnetpayment'))
    settlement_figure = settlement_figure_queryset['transnetpayment__sum']
    if settlement_figure is None:
        settlement_figure_vat = 0
    else:
        if agreement_type == 'Lease':
            settlement_figure_vat = settlement_figure * decimal.Decimal(sales_tax_rate)
        else:
            settlement_figure_vat = settlement_figure * decimal.Decimal(sales_tax_rate)

    first_rental_date = agreement_detail.agreementfirstpaymentdate

    # get Number of Document Fees
    try:
        doc_fee_count = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                                            transactionsourceid='GO1',
                                                                            transactiondate__lt=first_rental_date) \
                                                                            .count()
    except:
        doc_fee_count = 0

    # get Number of Primaries
    try:
        primary_count = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                                          transactionsourceid='GO1',
                                                                          transtypeid__isnull=True,
                                                                          transactiondate__gte=first_rental_date)\
                                                                          .count()
    except:
        primary_count = 0

    # get Number of Secondaries
    try:
        secondary_count = account_summary.filter(transactionsourceid__in=['GO2', 'GO3']).count()
    except:
        secondary_count = 0


    # Add Gross of Vat to account summary queryset
    row_index = 0
    for row in account_summary:
        if row.transactionsourceid in ['GO8','GO9'] and row.transvatpayment is not None:
            row.transgrosspayment = row.transnetpayment + row.transvatpayment

        else:
            row.transgrosspayment = row.transnetpayment * decimal.Decimal(sales_tax_rate)
        if row.transactionsourceid in ['GO1', 'GO2', 'GO3']:
            if row.transactiondate >= agreement_detail.agreementfirstpaymentdate:
                row_index += 1
        row.row_index = row_index

    # Add Gross of Vat to account detail queryset
    for row in account_detail:

        row.transvatpayment = row.transnetpayment * decimal.Decimal(0.2)

    # Return to Template
    return render(request, 'core_agreement_crud/agreement_management_detail.html',
                {'agreement_detail':agreement_detail,
                 'agreement_customer': agreement_customer,
                 'agreement_payable_net': agreement_payable_net,
                 'agreement_payable_gross':agreement_payable_gross,
                 'agreement_instalment_gross':agreement_instalment_gross,
                 'agreement_fees_net':agreement_fees_net,
                 'bacs_audit':bacs_audit,
                 'account_detail':account_detail,
                 'account_summary':account_summary,
                 'settlement_figure':settlement_figure,
                 'settlement_figure_vat':settlement_figure_vat,
                 'agreement_type':agreement_type,
                 'doc_fee_count':doc_fee_count,
                 'primary_count':primary_count,
                 'secondary_count':secondary_count,
                 'agreement_regulated_flag':agreement_regulated_flag,
                 'go_id':go_id
                 })


@login_required(login_url="signin")
def agreement_management_tab1(request):

    errors = {}
    context = {}

    template = 'core_agreement_crud/agreement_management_tab1.html'

    context['username'] = request.user

    risk_flag = True
    bamf_flag = True
    secondary_flag = True
    title_flag = True
    security_flag = True
    amf_flag = True

    if request.method == 'POST':

        try:

            a_id = re.sub('\\s+', '', request.POST['agreement_id'])
            a_type = request.POST['agreement_type']
            broker = request.POST['broker_type']
            funder = request.POST['funder_code']
            company = request.POST['company_name']
            risk_flag = request.POST['risk_flag'] or 0
            bamf_flag = request.POST['bamf_flag'] or 0
            secondary_flag = request.POST['secondary_flag'] or 0
            title_flag = request.POST['title_flag'] or 0
            security_flag = request.POST['security_flag'] or 0
            amf_flag = request.POST['amf_flag'] or 0

            if broker == 'Broker':
                risk_flag = 0
                bamf_flag = 0
                secondary_flag = 1
                title_flag = 1
                security_flag = 1
                amf_flag = 1

            customer_number = False

            addressline1 = request.POST['customeraddress1']
            addressline2 = request.POST['customeraddress2']
            addressline3 = request.POST['customeraddress3']
            addressline4 = request.POST['customeraddress4']
            addressline5 = request.POST['customeraddress5']
            addresspostcode = request.POST['customerpostcode']
            salesauthority = request.POST['agreementauthority']
            # contactname = request.POST['customercontact']
            firstname = request.POST['customerfirstname']
            surname = request.POST['customersurname']
            mobilephonenumber = request.POST['customermobilenumber']
            phonenumber = request.POST['customerphonenumber']
            email = request.POST['customeremail']
            company_ref_no = request.POST['company_ref_no']
            socialmedia1 = request.POST['social_media1']
            socialmedia2 = request.POST['social_media2']
            socialmedia3 = request.POST['social_media3']
            agreement_origin_flag = "GO"
            stage = "1"

            if validate_tab1(request.POST, errors):

                if request.POST.get('customernumber'):
                    customer_number = request.POST['customernumber']

                broker_rec = go_broker.objects.get(broker_description=broker)
                funder_rec = go_funder.objects.get(id=funder)
                # profile_rec = go_profile_types.objects.get(profile_description=p_type)
                agreement_def = go_agreement_definitions.objects.get(agreementdefname=a_type)

                # val_rec = go_agreement_id_definitions.objects.get(broker=broker_rec, profile_type=profile_rec,
                #                                                agreement_definitions=agreement_def)

                if validate_agreement_number(a_id, errors, 'agreement_id', broker):

                    go_id = uuid.uuid1()

                    # Step 1: Create go_id record
                    go_id_obj = go_agreement_index(go_id=go_id, agreement_id=a_id, user=request.user,
                                                   broker=broker_rec, company_ref_no=company_ref_no,
                                                   social_media1=socialmedia1, social_media2=socialmedia2,
                                                   social_media3=socialmedia3,
                                                   agreement_origin_flag=agreement_origin_flag,
                                                   risk_flag=risk_flag, bamf_flag=bamf_flag,
                                                   secondary_flag=secondary_flag, amf_flag=amf_flag,
                                                   title_flag=title_flag, security_flag=security_flag, funder=funder_rec)
                    go_id_obj.save()

                    new_rec = {
                        'go_id': go_id_obj,
                        'agreementnumber': a_id,
                        'agreementagreementtypeid': agreement_def
                    }

                    customer_rec = {
                        'customercompany': company,
                        'customeraddress1': addressline1,
                        'customeraddress2': addressline2,
                        'customeraddress3': addressline3,
                        'customeraddress4': addressline4,
                        'customeraddress5': addressline5,
                        'customerpostcode': addresspostcode,
                        'customercontact': firstname + ' ' + surname,
                        'customerfirstname': firstname,
                        'customersurname': surname,
                        'customermobilenumber': mobilephonenumber,
                        'customerphonenumber': phonenumber,
                        'customeremail': email
                    }

                    customer_action = None

                    if customer_number:
                        cust_obj = go_customers.objects.get(customernumber=customer_number)
                        for k in customer_rec:
                            setattr(cust_obj, k, customer_rec[k])
                        cust_obj.save()
                        if request.POST['customerchanges'] not in (0, "0"):
                            customer_action = 'update'

                    else:
                        customer_action = 'create'
                        customer_rec['customernumber'] = generate_customer_number()
                        cust_obj = go_customers(**customer_rec)
                        cust_obj.save()

                    go_agreement_1 = go_agreements(agreementcreator=request.user,
                                                   agreementauthority=salesauthority,
                                                   # agreement_stage=stage,
                                                   **new_rec)

                    go_agreement_2 = go_agreement_querydetail(customercompany=company,
                                                              agreementcustomernumber=cust_obj,
                                                              agreementcreator=request.user,
                                                              agreementauthority=salesauthority,
                                                              agreementdefname=agreement_def.agreementdefname,
                                                              agreement_stage=stage, **new_rec)
                    failed = 0
                    try:
                        go_id_obj.save()
                        failed = 1
                        go_agreement_1.save()
                        failed = 2
                        go_agreement_2.save()
                    except Exception as e:
                        if failed > 1:
                            go_agreement_1.delete()
                        if failed > 0:
                            go_id_obj.delete()

                    # agreement_querydetail.objects.filter(go_id=go_id).update(agreement_stage=stage)

                    url = reverse('core_agreement_crud:agreement_management_tab2', args=[a_id])
                    if customer_action:
                        url += '?customer_action={}'.format(customer_action)

                    return redirect(url)

        except Exception as e:
            context['error'] = e
            # context['error'] = '{} {}'.format(e, traceback.format_exc())

    context['profile_types'] = go_profile_types.objects.filter(selectable=True)
    context['sales_authorities'] = go_sales_authority.objects.filter(selectable=True)
    context['brokers'] = go_broker.objects.filter(selectable=True)
    context['funders'] = go_funder.objects.filter(selectable=True).order_by('funder_description')
    context['types'] = go_agreement_definitions.objects.filter(selectable=True)

    context['errors'] = errors

    context['values'] = request.POST.copy()
    if context['values'].get('funder_code'):
        context['values']['funder_code'] = int(context['values']['funder_code'])

    # Configure profile switches
    if context['errors'] or context['errors']:
        if request.POST.get('risk_flag', 0) == "1":
            context['risk_flag_on'] = True
        if request.POST.get('bamf_flag', 0) == "1":
            context['bamf_flag_on'] = True
        if request.POST.get('security_flag', 0) == "1":
            context['security_flag_on'] = True
        if request.POST.get('secondary_flag', 0) == "1":
            context['secondary_flag_on'] = True
        if request.POST.get('title_flag', 0) == "1":
            context['title_flag_on'] = True
        if request.POST.get('amf_flag', 0) == "1":
            context['amf_flag_on'] = True
    else:
        context['risk_flag_on'] = risk_flag
        context['bamf_flag_on'] = bamf_flag
        context['security_flag_on'] = security_flag
        context['secondary_flag_on'] = secondary_flag
        context['title_flag_on'] = title_flag
        context['amf_flag_on'] = amf_flag

    if (context.get('errors') or context.get('error')) and not request.POST.get('customernumber'):
        context['new_customer'] = True

    # print("errors")
    # print(errors)

    return render(request, template, context)


@login_required(login_url='signin')
def agreement_management_tab1_1(request, current_agreement_id):

    errors = {}
    error = None  # Global error
    context = {}

    try:
        transaction_summary_extract = go_account_transaction_summary.objects.filter(agreementnumber=current_agreement_id,
                                                                                    transactionbatch_id__contains='GO')
        context['transaction_summary_extract_count'] = transaction_summary_extract.count()
        transition = transition_log.objects.filter(agreementnumber=current_agreement_id)
        context['transition_count'] = transition.count()

    except:
        error = None

    template = 'core_agreement_crud/agreement_management_tab1.html'

    go_id_detail = None
    customer_detail = None
    agreement_detail = None

    bamf_flag = None
    risk_flag = None
    amf_flag = None
    security_flag = None
    title_flag = None
    secondary_flag = None

    values = request.POST.copy()

    context['username'] = request.user
    values['agreement_id'] = current_agreement_id

    try:
        go_id_detail = go_agreement_index.objects.get(agreement_id=current_agreement_id)
        agreement = go_agreements.objects.get(agreementnumber=current_agreement_id)
        agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=current_agreement_id)
        context['agreement_detail'] = agreement_detail
    except:
        print('failed')
        error = 'Agreement Number Not Found'

    if not error:
        try:
            customer_detail = go_customers.objects.get(customernumber=agreement_detail.agreementcustomernumber)
            context['agreement_customer'] = customer_detail
            context['agreement_customer_name'] = customer_detail.customercompany
        except:
            error = 'Customer Record Not Found'
            # error = None

    customer_fields = ('customeraddress1', 'customeraddress2', 'customeraddress3', 'customeraddress4',
                       'customeraddress5', 'customerpostcode', 'customermobilenumber',
                       'customerphonenumber', 'customeremail', 'customernumber', 'customerfirstname', 'customersurname')

    if not error:

        bamf_flag = go_id_detail.bamf_flag
        risk_flag = go_id_detail.risk_flag
        amf_flag = go_id_detail.amf_flag
        security_flag = go_id_detail.security_flag
        title_flag = go_id_detail.title_flag
        secondary_flag = go_id_detail.secondary_flag

        try:

            if request.method == 'GET':

                go_id_fields = ('broker', 'profile', 'company_ref_no', 'social_media1', 'social_media2', 'social_media3', 'agreement_origin_flag',)

                agreement_fields = ('agreementauthority', 'agreementcustomernumber')

                for f in go_id_fields:
                    values[f] = getattr(go_id_detail, f) or ''

                for f in customer_fields:
                    values[f] = getattr(customer_detail, f) or ''

                for f in agreement_fields:
                    values[f] = getattr(agreement_detail, f) or ''

                values['agreement_type'] = agreement_detail.agreementdefname
                values['company_name'] = agreement_detail.customercompany
                values['broker_type'] = go_id_detail.broker.broker_description
                values['funder_code'] = go_id_detail.funder.id

                # values['profile_type'] = go_id_detail.profile.profile_description

            if request.method == 'POST':

                if validate_tab1(request.POST, errors):

                    if request.POST.get('customernumber'):
                        customer_number = request.POST['customernumber']

                    broker_rec = go_broker.objects.get(broker_description=request.POST['broker_type'])
                    if request.POST.get('funder_code'):
                        funder_rec = go_funder.objects.get(id=request.POST['funder_code'])
                    # profile_rec = go_profile_types.objects.get(profile_description=p_type)
                    agreement_def = go_agreement_definitions.objects.get(agreementdefname=request.POST['agreement_type'])

                    # val_rec = go_agreement_id_definitions.objects.get(broker=broker_rec, profile_type=profile_rec,
                    #                                                agreement_definitions=agreement_def)

                    a_id = request.POST['agreement_id']
                    agreement_origin_flag = "GO"

                    process = False

                    validate_args = (a_id, errors, 'agreement_id', request.POST['broker_type'])
                    if validate_agreement_number(*validate_args, current_agreement_id=current_agreement_id):
                        process = True

                    if process:

                        new_go_id_detail = go_agreement_index.objects.get(agreement_id=current_agreement_id)

                        # Update go_id table
                        new_go_id_detail.user = request.user
                        new_go_id_detail.agreement_id = a_id
                        new_go_id_detail.broker = broker_rec
                        if request.POST.get('funder_code'):
                            new_go_id_detail.funder = funder_rec

                        risk_flag = request.POST.get('risk_flag')
                        bamf_flag = request.POST.get('bamf_flag')
                        secondary_flag = request.POST.get('secondary_flag')
                        security_flag = request.POST.get('security_flag')
                        title_flag = request.POST.get('title_flag')
                        amf_flag = request.POST.get('bamf_flag')

                        if request.POST['broker_type'] == 'Broker':
                            risk_flag = 0
                            bamf_flag = 0
                            secondary_flag = 1
                            security_flag = 1
                            title_flag = 1
                            amf_flag = 1
                        else:
                            amf_flag = 0

                        new_go_id_detail.social_media1 = request.POST['social_media1']
                        new_go_id_detail.social_media2 = request.POST['social_media2' ]
                        new_go_id_detail.social_media3 = request.POST['social_media3']
                        new_go_id_detail.company_ref_no = request.POST['company_ref_no']
                        new_go_id_detail.agreement_origin_flag = agreement_origin_flag
                        new_go_id_detail.risk_flag = risk_flag or 0
                        new_go_id_detail.bamf_flag = bamf_flag or 0
                        new_go_id_detail.secondary_flag = secondary_flag or 0
                        new_go_id_detail.title_flag = title_flag or 0
                        new_go_id_detail.security_flag = security_flag or 0
                        new_go_id_detail.amf_flag = amf_flag or 0
                        new_go_id_detail.save()

                        # Create/update customer table

                        customer_action = None

                        if request.POST['customernumber']:
                            cust_obj = go_customers.objects.get(customernumber=request.POST['customernumber'])
                            if request.POST['customerchanges'] not in (0, "0"):
                                customer_action = 'update'
                        else:
                            cust_obj = go_customers(customernumber=generate_customer_number())
                            customer_action = 'create'

                        for k in customer_fields:
                            if k != 'customernumber':
                                setattr(cust_obj, k, request.POST[k])

                        cust_obj.customercompany = request.POST['company_name']

                        cust_obj.save()

                        # Update agreement tables

                        update_values = {
                            'go_id': new_go_id_detail,
                            'agreementnumber': a_id,
                            'agreementagreementtypeid': agreement_def,
                            'agreementauthority': request.POST['agreementauthority'],
                            'agreementcustomernumber': cust_obj,
                            'customercompany': request.POST['company_name']
                        }
                        for k in update_values:
                            setattr(agreement, k, update_values[k])
                            setattr(agreement_detail, k, update_values[k])

                        # agreements(agreement_stage=stage).save()

                        agreement.save()

                        agreement_detail.agreementdefname = agreement_def.agreementdefname

                        agreement_detail.save()
                        if go_account_transaction_summary.objects.filter(go_id=new_go_id_detail).exclude(transactionbatch_id='').exclude(transactionbatch_id__isnull=True).count() == 0:
                            recalculate_function(a_id)


                        url = reverse('core_agreement_crud:agreement_management_tab2', args=[a_id])
                        if customer_action:
                            url += '?customer_action={}'.format(customer_action)

                        return redirect(url)

                values = request.POST

        except Exception as e:
            error = '{} {}'.format(e, traceback.format_exc())

    if (error or error) and not request.POST.get('customernumber'):
        context['new_customer'] = True

    # Template vars

    context['error'] = error
    context['errors'] = errors
    context['values'] = values
    context['go_id_detail'] = go_id_detail

    # context['profile_types'] = go_profile_types.objects.filter(selectable=True)
    context['sales_authorities'] = go_sales_authority.objects.filter(selectable=True)
    context['brokers'] = go_broker.objects.filter(selectable=True)
    context['types'] = go_agreement_definitions.objects.filter(selectable=True)
    context['funders'] = go_funder.objects.filter(selectable=True).order_by('funder_description')

    context['update'] = True

    context['agreement_id'] = current_agreement_id

    # print('go_id.funder:', go_id_detail.funder)
    # print('values.funder_code:', values.get('funder_code'))
    # print('values.broker_type:', values.get('broker_type'))

    # Configure profile switches
    if context['errors'] or context['errors']:
        if request.POST.get('risk_flag', 0) == "1":
            context['risk_flag_on'] = True
        if request.POST.get('bamf_flag', 0) == "1":
            context['bamf_flag_on'] = True
        if request.POST.get('security_flag', 0) == "1":
            context['security_flag_on'] = True
        if request.POST.get('secondary_flag', 0) == "1":
            context['secondary_flag_on'] = True
        if request.POST.get('title_flag', 0) == "1":
            context['title_flag_on'] = True
        if request.POST.get('amf_flag', 0) == "1":
            context['amf_flag_on'] = True
    else:
        context['risk_flag_on'] = risk_flag
        context['bamf_flag_on'] = bamf_flag
        context['security_flag_on'] = security_flag
        context['secondary_flag_on'] = secondary_flag
        context['title_flag_on'] = title_flag
        context['amf_flag_on'] = amf_flag

    return render(request, template, context)


@login_required(login_url='signin')
def agreement_management_tab2(request, agreement_id):

    error = None
    errors = {}
    values = {}
    context = {'agreement_id': agreement_id}
    template = 'core_agreement_crud/agreement_management_tab2.html'

    go_id = None
    agreement_detail = None

    try:
        transaction_summary_extract = go_account_transaction_summary.objects.filter(agreementnumber=agreement_id,
                                                                                    transactionbatch_id__contains='GO')
        context['transaction_summary_extract_count'] = transaction_summary_extract.count()
        transition = transition_log.objects.filter(agreementnumber=agreement_id)
        context['transition_count'] = transition.count()
    except:
        error = None

    try:
        go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
        agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
        context['agreement_detail'] = agreement_detail
        agreement_customer = go_customers.objects.get(customernumber=agreement_detail.agreementcustomernumber)
        context['agreement_customer'] = agreement_customer
        context['username'] = request.user
        context['batches'] = []
        for row in DrawDown.objects.filter(due_date__gte=datetime.datetime.now(), status='OPEN', agreement_id=agreement_id):
            context['batches'].append(json.dumps({'batch_header': row.batch_header.reference,
                                                  'created': row.created.strftime("%d/%m/%Y"),
                                                  'user': row.user.username if row.user else None}))
        context['batches'] = json.dumps(context['batches'])
    except Exception as e:
        error = str(e)

    if not error:

        if request.method == 'GET':

            try:

                agreement_date_fields = ('agreementagreementdate', 'agreementupfrontdate', 'agreementfirstpaymentdate')

                agreement_fields = ('agreementbankreference', 'agreementbanksortcode', 'agreementresidualdate',
                                    'agreementbankaccountnumber', 'agreementbankaccountname')

                for f in agreement_date_fields:
                    dt = getattr(agreement_detail, f)
                    if dt and isinstance(dt, datetime.datetime):
                        values[f] = dt.strftime("%Y-%m-%d")

                for f in agreement_fields:
                    if go_id.manual_payments:
                        values[f] = ''
                    else:
                        values[f] = getattr(agreement_detail, f)

                values['agreementresidualdate'] = agreement_detail.agreementresidualdate

                values['term'] = go_id.term

                if values['agreementresidualdate'] and isinstance(values['agreementresidualdate'], datetime.datetime):
                    values['agreementresidualdate'] = values['agreementresidualdate'].strftime("%d/%m/%Y")

                if not values['agreementbankreference']:
                    values['agreementbankreference'] = generate_dd_reference(agreement_id)

                for k in values.keys():
                    if values[k] is None:
                        values[k] = ''

            except Exception as e:
                tb = traceback.format_exc()
                error = '{} {}'.format(e, tb)

        if request.method == 'POST':

            values = request.POST

            try:

                agreementdate = request.POST.get('agreementagreementdate')

                termlength = request.POST.get('term')

                upfrontdate =request.POST.get('agreementupfrontdate')

                firstpaydate =request.POST.get('agreementfirstpaymentdate')

                residualdate = request.POST.get('agreementresidualdate')

                collectiontype = request.POST.get('agreementcollectiontype')

                ddiref = request.POST.get('agreementbankreference')

                accountname = request.POST.get('agreementbankaccountname')

                sortcode = request.POST.get('agreementbanksortcode')

                accountnumber = request.POST.get('agreementbankaccountnumber')

                if request.POST.get('manual_payments'):
                    if DrawDown.objects.filter(status='OPEN', agreement_id=agreement_id).exists():
                        raise Exception("This agreement has a transaction that is currently in an open batch.")
                    try:
                        manual_payments = int(request.POST.get('manual_payments', 0)) or 0
                    except:
                        manual_payments = 0
                else :
                    manual_payments = 0

                stage = "2"
                if agreement_detail.agreement_stage < str(requiredtabs()):
                    go_agreement_querydetail.objects.filter(go_id=go_id).update(agreement_stage=stage)

                if not agreementdate:
                    errors['agreementagreementdate'] = 'Agreement Date Required'
                elif not validate_date(agreementdate):
                    errors['agreementagreementdate'] = 'Agreement Date Invalid'

                if not termlength:
                    errors['term'] = 'Term Length Required'

                if not firstpaydate:
                    errors['agreementfirstpaymentdate'] = 'First Due Date Required'
                elif not validate_date(firstpaydate):
                    errors['agreementfirstpaymentdate'] = 'First Due Date Invalid'
                else:
                    firstpaydate_dt = datetime.datetime.strptime(firstpaydate, "%Y-%m-%d")
                    if int(firstpaydate_dt.strftime("%d")) > 28:
                        errors['agreementfirstpaymentdate'] = 'First Due Date Must Not Exceed 28th'

                if not residualdate:
                    errors['agreementresidualdate'] = 'Invalid Term Length / First Due Date'
                elif not validate_date(residualdate, format="%d/%m/%Y"):
                    errors['agreementresidualdate'] = 'Last Primary Date Invalid'

                if not upfrontdate:
                    errors['agreementupfrontdate'] = 'Upfront Date Required'
                elif not validate_date(upfrontdate):
                    errors['agreementupfrontdate'] = 'Upfront Date Invalid'

                if not manual_payments:

                    if not ddiref:
                        errors['agreementbankreference'] = 'Direct Debit Instruction Reference Required'

                    if not accountname:
                        errors['agreementbankaccountname'] = 'Account Name Required'

                    if not sortcode:
                        errors['agreementbanksortcode'] = 'Sort Code Required'

                    if not accountnumber:
                        errors['agreementbankaccountnumber'] = 'Account Number Required'

                    if accountnumber:
                        if len(accountnumber) != 8:
                            errors['agreementbankaccountnumber'] = 'Account Number must be 8 digits'
                        elif not re.search(r'^\d+$', accountnumber):
                            errors['agreementbankaccountnumber'] = 'Account Number must contain digits only'

                    if sortcode:
                        if len(sortcode) != 6:
                            errors['agreementbanksortcode'] = 'Sort Code must be 6 digits'
                        elif not re.search(r'^\d+$', sortcode):
                            errors['agreementbanksortcode'] = 'Sort Code must contain digits only'



                create_ddi = True

                if not errors:

                    residualdate = datetime.datetime.strptime(residualdate, "%d/%m/%Y")

                    if manual_payments:
                        if go_id.funder.provider == 'datacash':
                            cancel_ddi_with_datacash(agreement_id)
                            create_ddi = False
                        # elif go_id.funder.provider == 'eazycollect':
                        #     cancel_contract(agreement_id)
                        #     create_ddi = False

                    if ddiref == agreement_detail.agreementbankreference and accountname == agreement_detail.agreementbankaccountname and accountnumber == agreement_detail.agreementbankaccountnumber and sortcode == agreement_detail.agreementbanksortcode:
                        print(ddiref)
                        print(agreement_detail.agreementbankreference)
                        create_ddi = False
                    else:
                        create_ddi = True

                    print(accountnumber)
                    print(agreement_detail.agreementbankaccountnumber)

                    if create_ddi:
                        search_args = {
                            'reference': ddiref,
                            'sequence': 9999,
                            'agreement_no': agreement_id,
                            'account_number': accountnumber,
                            'sort_code': sortcode,
                            'account_name': accountname,
                            'provider': go_id.funder.provider

                        }
                        if DDHistory.objects.filter(**search_args).exists():
                            # They're just tabbing through. Don't process.
                            create_ddi = False

                    if create_ddi:
                        if DDHistory.objects.filter(reference=ddiref).exists():
                            errors['agreementbankreference'] = 'This Direct Debit Instruction Reference has been used previously.'

                if not errors:

                    if create_ddi:

                        try:
                            if go_id.funder.provider == 'datacash':
                                context['reference'] = create_ddi_with_datacash(
                                    agreement_id,
                                    request.POST['agreementbankreference'],
                                    request.POST['agreementbankaccountname'],
                                    request.POST['agreementbankaccountnumber'],
                                    request.POST['agreementbanksortcode'],
                                    request.user
                                )
                            elif go_id.funder.provider == 'eazycollect':
                                create_ddi_with_eazycollect(agreement_id,
                                                            request.POST['agreementbankreference'],
                                                            request.POST['agreementbankaccountname'],
                                                            request.POST['agreementbankaccountnumber'],
                                                            request.POST['agreementbanksortcode'],
                                                            user=request.user)
                            else:
                                raise Exception("FATAL: Unknown Provider.")
                            # TODO: Cater for Eazycollect
                        except Exception as e:
                            context['datacash_failed'] = True
                            if str(e) == 'Invalid CLIENT/PASS':
                                context['datacash_failed_fatal'] = True
                            elif str(e) == 'FATAL: Unknown Provider.':
                                context['datacash_failed_fatal'] = True
                            elif str(e) == 'Datacash Service Unavailable':
                                context['datacash_failed_fatal'] = True

                        if context.get('reference'):
                            update_ddi_status(agreement_id, 'Active DD')
                        else:
                            update_ddi_status(agreement_id, 'Inactive DD')

                    agreement_rec = {
                        # 'agreement_stage' = stage,
                        'agreementagreementdate': agreementdate,
                        'agreementupfrontdate': upfrontdate,
                        'agreementfirstpaymentdate': firstpaydate,
                        'agreementresidualdate': residualdate,
                        'agreementcollectiontype': 1,
                        'agreementbankreference': ddiref,
                        'agreementbankaccountname': accountname,
                        'agreementbanksortcode': sortcode,
                        'agreementbankaccountnumber': accountnumber,
                        'agreementcreatedate' : datetime.datetime.now(),
                    }

                    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
                    go_agreements.objects.filter(go_id=go_id).update(**agreement_rec)
                    go_agreement_querydetail.objects.filter(go_id=go_id).update(**agreement_rec)

                    # apellio_extension_code = go_extensions.objects.filter(ap_extension_sequence=1)
                    # client_configuration.objects.filter(client_id=apellio_extension_code)

                    go_id.term = termlength
                    go_id.manual_payments = manual_payments
                    go_id.save()

                    context['term'] = termlength
                    context['agreementfirstpaymentdate'] = firstpaydate
                    if go_account_transaction_summary.objects.filter(go_id=go_id).exclude(transactionbatch_id='').exclude(transactionbatch_id__isnull=True).count() == 0:
                        recalculate_function(agreement_id)

                    if not context.get('datacash_failed'):
                        url = reverse('core_agreement_crud:agreement_management_tab3', args=[agreement_id])
                        if create_ddi and not manual_payments:
                            url += '?datacash_request=1'
                        return redirect(url)

            except Exception as e:
                error = str(e)
                # error = '{} {}'.format(e, traceback.format_exc())

    context['error'] = error
    context['errors'] = errors
    context['values'] = values
    context['go_id'] = go_id
    context['customer_action'] = request.GET.get('customer_action')

    holidays = get_holidays()
    context['holidays'] = holidays

    days_before_dd_call = daysbeforecalldd()
    context['days_before_dd_call'] = days_before_dd_call

    days_before_setup_active = daysbeforeddsetup()
    if agreement_detail:
        if not agreement_detail.agreement_stage < str(requiredtabs()):
            context['next_due_date'] = get_next_due_date(agreement_id) or '2999-12-31'

    context['setup_active_date'] = numpy.busday_offset(datetime.datetime.today(), days_before_setup_active,
                                                       roll='forward', holidays=holidays).astype(datetime.date)

    context['call_active_date'] = numpy.busday_offset(datetime.datetime.today(),
                                                      days_before_dd_call + days_before_setup_active,
                                                      roll='forward', holidays=holidays).astype(datetime.date)

    context['days_before_setup_active'] = days_before_setup_active

    context['manual_payments_display'] = go_id.manual_payments
    if errors:
        context['manual_payments_display'] = int(request.POST.get('manual_payments'))

    return render(request, template, context)


@login_required(login_url='signin')
def agreement_management_tab3(request, agreement_id):

    error = None
    errors = {}
    values = {}
    context = {'agreement_id': agreement_id}
    template = 'core_agreement_crud/agreement_management_tab3.html'

    context['agreementfirstpaymentdate'] = go_agreements.agreementfirstpaymentdate
    context['agreementupfrontdate'] = go_agreements.agreementupfrontdate
    context['agreementfirstpaymentdate'] = go_agreements.agreementfirstpaymentdate
    context['agreementresidualdate'] = go_agreements.agreementresidualdate
    context['agreementagreementdate'] = go_agreements.agreementagreementdate
    # context['agreementcreatedate'] = go_agreements.agreementcreatedate
    context['agreementauthority'] = go_agreements.agreementauthority
    context['agreement_customer'] = go_agreements.agreementcustomernumber
    # context['agreementdefname'] = agreements.agreementdefname

    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    config = client_configuration.objects.get(client_id="NWCF")
    

    context['agreement_detail'] = agreement_detail

    # agreement_customer = customers.objects.get(customernumber=agreement_detail.agreementcustomernumber)
    context['agreement_customer'] = go_customers.customernumber

    account_detail = go_account_transaction_detail
    context['account_detail'] = account_detail

    context['username'] = request.user

    go_id = None
    agreement_detail = None
    account_detail = None

    try:
        transaction_summary_extract = go_account_transaction_summary.objects.filter(agreementnumber=agreement_id,
                                                                                    transactionbatch_id__contains='GO')
        context['transaction_summary_extract_count'] = transaction_summary_extract.count()
        transition = transition_log.objects.filter(agreementnumber=agreement_id)
        context['transition_count'] = transition.count()

    except:
        error = None

    try:
        go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
        agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)

        context['agreement_detail'] = agreement_detail
        context['term'] = go_id.term

        # context['pro#file'] = go_id.pro#file_id
        context['broker'] = go_id.broker_id

        context['agreementfirstpaymentdate'] = go_agreement_querydetail.agreementfirstpaymentdate

    except:
        error = 'Agreement Number Not Found'

    if not error:
        if go_id.consolidation_info:
            context['consolidations'] = ', '.join(go_id.consolidation_info.split("::"))

    if request.method == 'GET' and not error:

        try:

            go_fields = ('agreement_instalment_gross', 'agreement_total_fees',
                         'agreement_payable_net', 'agreement_payable_gross')

            agreement_fields = ('agreementinstalmentnet', 'agreementinstalmentvat', 'agreementoriginalprincipal',
                                'agreementcharges')

            for f in go_fields:
                values[f] = getattr(go_id, f)

            for f in agreement_fields:
                values[f] = getattr(agreement_detail, f)

            values['doc_fee'] = go_id.agreement_doc_fee
            values['risk_fee'] = go_id.agreement_risk_fee
            # values['bamf_fee'] = go_id.agreement_bamf_fee

            for k in values.keys():
                if values[k] is None:
                    values[k] = ''
                if values[k] and isinstance(values[k], Decimal):
                    values[k] = '{0:0,.2f}'.format(values[k])

            values['DateImplemented'] = datetime.date.today().strftime("%d/%m/%Y")

        except Exception as e:
            error = e

    if request.method == 'POST' and not error:

        values = request.POST

        try:

            docfee = request.POST['doc_fee']
            instalmentnet = request.POST['agreementinstalmentnet']
            instalmentvat = request.POST['agreementinstalmentvat']
            instalmentgross = request.POST['agreement_instalment_gross']
            principal = request.POST['agreementoriginalprincipal']
            charges = request.POST['agreementcharges']
            totalfees = request.POST['agreement_total_fees']
            payablenet = request.POST['agreement_payable_net']
            payablegross = request.POST['agreement_payable_gross']

            if go_id.broker_id == 1:
                riskfee = request.POST['risk_fee']
            else:
                riskfee = '0.00'
            # bamffee = request.POST['bamf_fee']
            date_implemented = request.POST['DateImplemented']

            if not docfee:
                errors['doc_fee'] = 'Doc Fee Required'

            if not instalmentnet:
                errors['agreementinstalmentnet'] = 'Instalment Amount Required'

            if not principal:
                errors['agreementoriginalprincipal'] = 'Principal Amount Required'

            # if principal < instalmentnet:
            #     errors['agreementoriginalprincipal'] = 'Principal should be greater than Instalments'

            if charges:
                if float(re.sub(',', '', charges)) < float(0):
                    errors['agreementcharges'] = 'Negative Charges'

            # if float(charges) /float(principal) > 5:
            #     errors['agreementoriginalprincipal'] = 'Charges Too High'


            # Decimal(re.sub(',', '', principal)

            #1.08 = commission

            # if principal+charges
            # 0.0125 = 0.15/12 = yield (15000*1.08)

            # a = (Decimal(re.sub(',', '', principal))) * Decimal(1.08)
            #
            if instalmentnet and charges:
                pmt_validation = -pmt(float(pmt_yield()), go_id.term, (float(re.sub(',', '', principal)))*float(pmt_commission()))
                if pmt_validation > (float(re.sub(',', '', instalmentnet))) and not request.POST.get('pmt_failed_but_continue'):
                    # print(pmt_validation)
                    errors['agreementoriginalprincipal'] = 'Please Check Principal and Instalments'
                    errors['agreementinstalmentnet'] = 'Please Check Principal and Instalments'
                    context['pmt_failed'] = True

            # if not context.get('pmt_failed'):
            #     url = reverse('core_agreement_crud:agreement_management_tab4', args=[agreement_id])
            #     url += '?pmt_request=1'
            #     return redirect(url)

            # c = b*go_id.term
            transactions = go_account_transaction_summary.objects.filter(go_id=go_id).exclude(transactionbatch_id='').exclude(transactionbatch_id__isnull=True).count()
            if not context.get('pmt_failed') and transactions == 0:
                if not errors:
                    go_account_transaction_summary.objects.filter(go_id=go_id, transactionsourceid='GO1').delete()
                    go_account_transaction_summary.objects.filter(go_id=go_id, transactionsourceid='GO3').delete()
                    go_account_transaction_detail.objects.filter(go_id=go_id, transactionsourceid='GO1').delete()
                    go_account_transaction_detail.objects.filter(go_id=go_id, transactionsourceid='GO3').delete()
                    agreement_rec = {
                        'agreementinstalmentnet': Decimal(re.sub(',', '', instalmentnet)),
                        'agreementinstalmentvat': Decimal(re.sub(',', '', instalmentvat)),
                        'agreementoriginalprincipal': Decimal(re.sub(',', '', principal)),
                        'agreementcharges': Decimal(re.sub(',', '', charges))
                    }
                    go_agreements.objects.filter(go_id=go_id).update(**agreement_rec)
                    go_agreement_querydetail.objects.filter(go_id=go_id).update(**agreement_rec)

                    go_id.agreement_doc_fee = Decimal(re.sub(',', '', docfee))
                    go_id.agreement_instalment_gross = Decimal(re.sub(',', '', instalmentgross))
                    go_id.agreement_total_fees = Decimal(re.sub(',', '', totalfees))
                    go_id.agreement_payable_net = Decimal(re.sub(',', '', payablenet))
                    go_id.agreement_payable_gross = Decimal(re.sub(',', '', payablegross))

                    go_id.agreement_risk_fee = Decimal(re.sub(',', '', riskfee))

                    # go_id.agreement_bamf_fee = Decimal(re.sub(',', '', bamffee))
                    # go_id.agreement_stage= stage
                    go_id.save()
                    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
                    stage = "3"
                    if agreement_detail.agreement_stage < str(requiredtabs()):
                        go_agreement_querydetail.objects.filter(go_id=go_id).update(agreement_stage=stage, agreementclosedflag = '901')

                    docfee_rec = {'go_id': go_id,
                                  'agreementnumber': go_id,
                                  'transtypeid' : '1',
                                  'transactiondate': agreement_detail.agreementupfrontdate,
                                  'transactionsourceid' : 'GO1',
                                  'transtypedesc' : 'Documentation Fee',
                                  'transflag' : 'Fee',
                                  'transfallendue' : '1',
                                  'transnetpayment': Decimal(re.sub(',', '', docfee)),
                                  'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                                  'transpayprointerest': Decimal(re.sub(',', '', docfee)),
                                  }


                    ats_docfee_rec = {'go_id': go_id,
                                      'agreementnumber': go_id,
                                      'transtypeid': '1',
                                      'transactiondate': agreement_detail.agreementupfrontdate,
                                      'transactionsourceid': 'GO1',
                                      'transtypedesc': '',
                                      'transflag': '',
                                      'transfallendue': '1',
                                      'transnetpayment': Decimal(re.sub(',', '', docfee)),
                                      'transgrosspayment': round(Decimal(re.sub(',', '', docfee))*Decimal(config.other_sales_tax),2),
                                      'transactionsourcedesc' : 'Primary',
                                      'transagreementagreementdate' : agreement_detail.agreementagreementdate,
                                      'transagreementauthority' : agreement_detail.agreementauthority,
                                      'transagreementclosedflag_id': '901',
                                      'transactionstatus':'905',
                                      'transagreementcustomernumber' : agreement_detail.agreementcustomernumber,
                                      # 'transagreementcustomernumber' : agreement_detail.agreementcustomernumber,
                                      'transcustomercompany': agreement_detail.customercompany,
                                      'transagreementddstatus_id' : agreement_detail.agreementddstatus_id,
                                      'transagreementdefname' : 'Lease Agreement',
                                      # 'transcustomercompany': customers.customernumber,
                                      'transddpayment' : '0' ,
                                      # 'transgrosspayment':,
                                      'transnetpaymentcapital': Decimal(re.sub(',', '', '0.00')),
                                      'transnetpaymentinterest': Decimal(re.sub(',', '', docfee)),
                                      }
                    if agreement_detail.agreementdefname == 'Hire Purchase':
                        ats_docfee_rec['transagreementdefname'] = 'Hire Purchase'
                        ats_docfee_rec['transgrosspayment'] = Decimal(re.sub(',', '', docfee))

                    go_account_transaction_detail(**docfee_rec).save()
                    go_account_transaction_summary(**ats_docfee_rec).save()

                    if go_id.broker_id == 2 :

                        docfee2_rec = {'go_id': go_id,
                                       'agreementnumber': go_id,
                                       'transtypeid': '4',
                                       'transactiondate': agreement_detail.agreementupfrontdate + timedelta(seconds=1),
                                       'transactionsourceid': 'GO1',
                                       'transtypedesc': 'Documentation Fee 2',
                                       'transflag': 'Fee',
                                       'transfallendue': '1',
                                       'transnetpayment': Decimal(re.sub(',', '', instalmentnet)),
                                       'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                                       'transpayprointerest': Decimal(re.sub(',', '', instalmentnet)),
                                       }

                        ats_docfee2_rec = {'go_id': go_id,
                                          'agreementnumber': go_id,
                                          'transtypeid': '4',
                                          'transactiondate': agreement_detail.agreementupfrontdate + timedelta(seconds=1),
                                          'transactionsourceid': 'GO1',
                                          'transtypedesc': '',
                                          'transflag': '',
                                          'transfallendue': '0',
                                          'transnetpayment': Decimal(re.sub(',', '', instalmentnet)),
                                          'transgrosspayment': round(Decimal(re.sub(',', '', instalmentnet))*Decimal(config.other_sales_tax),2),
                                          'transactionsourcedesc': 'Primary',
                                          'transagreementagreementdate': agreement_detail.agreementagreementdate,
                                          'transagreementauthority': agreement_detail.agreementauthority,
                                          'transagreementclosedflag_id': '901',
                                          'transactionstatus': '905',
                                          'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                                          'transcustomercompany': agreement_detail.customercompany,
                                          'transagreementddstatus_id': agreement_detail.agreementddstatus_id,
                                          'transagreementdefname': 'Lease Agreement',
                                          # 'transcustomercompany': customers.customernumber,
                                          'transddpayment': '0',
                                          # 'transgrosspayment':,
                                          'transnetpaymentcapital': Decimal(re.sub(',', '', '0.00')),
                                          'transnetpaymentinterest': Decimal(re.sub(',', '', instalmentnet)),
                                          }
                        if agreement_detail.agreementdefname == 'Hire Purchase':
                            ats_docfee2_rec['transagreementdefname'] = 'Hire Purchase'
                            ats_docfee2_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet))

                        go_account_transaction_detail(**docfee2_rec).save()
                        go_account_transaction_summary(**ats_docfee2_rec).save()

                    Interest = go_id.term* Decimal(re.sub(',', '', instalmentnet)) -  Decimal(re.sub(',', '', principal))

                    multiplier=(go_id.term)*(go_id.term+1)/2
                    multiplier2= Decimal(Interest)/Decimal(multiplier)
                    for i in range(go_id.term):
                        ats_rentals_rec = {'go_id': go_id,
                                           'agreementnumber': agreement_id,
                                           'transtypeid': '0',
                                           'transactiondate': agreement_detail.agreementfirstpaymentdate + relativedelta(months=+i),
                                           'transactionsourceid': 'GO1',
                                           'transtypedesc': '',
                                           'transflag': '',
                                           'transfallendue': '0',
                                           'transnetpayment': Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee)),
                                           'transgrosspayment': round((Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee)))*Decimal(config.other_sales_tax),2),
                                           'transactionsourcedesc' : 'Primary',
                                           'transagreementagreementdate': agreement_detail.agreementagreementdate,
                                           'transagreementauthority': agreement_detail.agreementauthority,
                                           'transagreementclosedflag_id': '901',
                                           'transactionstatus': '905',
                                           'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                                           'transcustomercompany': agreement_detail.customercompany,
                                           'transagreementddstatus_id': agreement_detail.agreementddstatus_id,
                                           'transagreementdefname': 'Lease Agreement',
                                           # 'transcustomercompany': customers.customernumber,
                                           'transddpayment': '1',
                                           # 'transgrosspayment':,
                                           'transnetpaymentinterest': round((go_id.term - i) * Decimal(multiplier2) + Decimal(re.sub(',', '', riskfee)),2),
                                           'transnetpaymentcapital': round(Decimal(re.sub(',', '', instalmentnet))-(go_id.term - i) * Decimal(multiplier2),2),
                                           }
                        if agreement_detail.agreementdefname == 'Hire Purchase':
                            ats_rentals_rec['transagreementdefname'] = 'Hire Purchase'
                            ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee))

                        if go_id.broker_id == 1:
                            if i > 0 and (i+1) % 6 == 0 and go_id.risk_flag == 1 and go_id.bamf_flag == 1:
                                ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                                    re.sub(',', '', riskfee)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))
                                ats_rentals_rec['transnetpaymentinterest'] = round((go_id.term - i) * Decimal(multiplier2) + Decimal(re.sub(',', '', riskfee)) + Decimal(
                                    re.sub(',', '', str(config.bamf_fee_amount_net))),2)
                                ats_rentals_rec['transgrosspayment'] = round((Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                                    re.sub(',', '', riskfee)))*Decimal(config.other_sales_tax) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_vat))),2)
                                if agreement_detail.agreementdefname == 'Hire Purchase':
                                    ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))
                        else:
                            if i > 0 and (i+1) % 12 == 0:
                                ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                                    re.sub(',', '', riskfee)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))
                                ats_rentals_rec['transnetpaymentinterest'] = round((go_id.term - i) * Decimal(multiplier2) + Decimal(re.sub(',', '', riskfee)) + Decimal(
                                    re.sub(',', '', str(config.bamf_fee_amount_net))),2)
                                ats_rentals_rec['transgrosspayment'] = round((Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                                    re.sub(',', '', riskfee)))*Decimal(config.other_sales_tax) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_vat))),2)
                                if agreement_detail.agreementdefname == 'Hire Purchase':
                                    ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))

                        if go_id.risk_flag == 1 and go_id.bamf_flag == 0:
                            ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee))
                            ats_rentals_rec['transnetpaymentinterest'] = round((go_id.term - i) * Decimal(multiplier2) + Decimal(re.sub(',', '', riskfee)),2)
                            ats_rentals_rec['transgrosspayment'] = round((Decimal(re.sub(',', '', instalmentnet))*Decimal(config.other_sales_tax) + Decimal(re.sub(',', '', riskfee))*Decimal(config.other_sales_tax)),2)
                            if agreement_detail.agreementdefname == 'Hire Purchase':
                                ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee))


                        if go_id.broker_id == 1:
                            if i > 0 and (i+1) % 6 == 0 and go_id.risk_flag == 0 and go_id.bamf_flag == 1 :
                                ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))
                                ats_rentals_rec['transnetpaymentinterest'] = round((go_id.term - i) * Decimal(multiplier2) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net))),2)
                                ats_rentals_rec['transgrosspayment'] = round((Decimal(re.sub(',', '', instalmentnet)))*Decimal(config.other_sales_tax) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_vat))),2)
                                if agreement_detail.agreementdefname == 'Hire Purchase':
                                    ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))
                        else:
                            if i > 0 and (i + 1) % 12 == 0:
                                ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))
                                ats_rentals_rec['transnetpaymentinterest'] = round((go_id.term - i) * Decimal(multiplier2) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net))),2)
                                ats_rentals_rec['transgrosspayment'] = round(
                                    (Decimal(re.sub(',', '', instalmentnet))) * Decimal(config.other_sales_tax) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_vat))), 2)
                                if agreement_detail.agreementdefname == 'Hire Purchase':
                                    ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))

                        if go_id.risk_flag == 0 and go_id.bamf_flag == 0 and go_id.broker_id == 1:
                            ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet))
                            ats_rentals_rec['transnetpaymentinterest'] = round((go_id.term - i) * Decimal(multiplier2),2)
                            ats_rentals_rec['transgrosspayment'] = round(Decimal(re.sub(',', '', instalmentnet)) * Decimal(config.other_sales_tax), 2)
                            if agreement_detail.agreementdefname == 'Hire Purchase':
                                ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet))

                        go_account_transaction_summary(**ats_rentals_rec).save()

                        atd_rentals_rec = {'go_id': go_id,
                                           'agreementnumber': agreement_id,
                                           # 'transtypeid': '1',
                                           'transactiondate': agreement_detail.agreementfirstpaymentdate + relativedelta(months=+i),
                                           'transactionsourceid': 'GO1',
                                           # 'transtypedesc': 'Documentation Fee',
                                           'transflag': 'Pay',
                                           'transfallendue': '0',
                                           'transnetpayment': Decimal(re.sub(',', '', instalmentnet)),
                                           'transpayproprincipal': round(Decimal(re.sub(',', '', instalmentnet)) - (go_id.term - i) * Decimal(multiplier2), 2),
                                           'transpayprointerest': round((go_id.term - i) * Decimal(multiplier2),2),
                                           }
                        go_account_transaction_detail(**atd_rentals_rec).save()

                        atd_risk_rec = {'go_id': go_id,
                                        'agreementnumber': agreement_id,
                                        'transtypeid': '3',
                                        'transactiondate': agreement_detail.agreementfirstpaymentdate + relativedelta(months=+i),
                                        'transactionsourceid': 'GO1',
                                        'transtypedesc': 'Risk Fee',
                                        'transflag': 'Fee',
                                        'transfallendue': '0',
                                        'transnetpayment': Decimal(re.sub(',', '', riskfee)),
                                        'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                                        'transpayprointerest': Decimal(re.sub(',', '', riskfee)),
                                        }
                        if go_id.risk_flag == 1:
                            if go_id.broker_id == 1:
                                go_account_transaction_detail(**atd_risk_rec).save()
                    for i in range(go_id.term):
                        if go_id.bamf_flag == 1:
                            if i > 0 and (i+1) % 6 == 0:
                                atd_BAMF_rec = {'go_id': go_id,
                                                'agreementnumber': agreement_id,
                                                'transtypeid': '5',
                                                'transactiondate': agreement_detail.agreementfirstpaymentdate + relativedelta(months=+i),
                                                'transactionsourceid': 'GO1',
                                                'transtypedesc': 'Bi-Annual Management Fee',
                                                'transflag': 'Fee',
                                                'transfallendue': '0',
                                                'transnetpayment' : str(config.bamf_fee_amount_net),
                                                'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                                                'transpayprointerest': str(config.bamf_fee_amount_net),
                                                }
                                if go_id.bamf_flag == 1:
                                    go_account_transaction_detail(**atd_BAMF_rec).save()
                        if go_id.broker_id == 2:
                            if go_id.amf_flag == 1:
                                if i > 0 and (i + 1) % 12 == 0:
                                    atd_BAMF_rec = {'go_id': go_id,
                                                    'agreementnumber': agreement_id,
                                                    'transtypeid': '2',
                                                    'transactiondate': agreement_detail.agreementfirstpaymentdate + relativedelta(months=+i),
                                                    'transactionsourceid': 'GO1',
                                                    'transtypedesc': 'Annual Management Fee',
                                                    'transflag': 'Fee',
                                                    'transfallendue': '0',
                                                    'transnetpayment': str(config.bamf_fee_amount_net),
                                                    'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                                                    'transpayprointerest': str(config.bamf_fee_amount_net),
                                                    }
                                    go_account_transaction_detail(**atd_BAMF_rec).save()

                    for i in range(3):
                        ats_secondary_rec = {'go_id': go_id,
                                             'agreementnumber': agreement_id,
                                             'transtypeid': '0',
                                             'transactiondate': agreement_detail.agreementresidualdate + relativedelta(months=+(i+1)),
                                             'transactionsourceid': 'GO3',
                                             'transtypedesc': '',
                                             'transflag': '',
                                             'transfallendue': '0',
                                             'transnetpayment': Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee)),
                                             'transgrosspayment': round((Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee)))*Decimal(config.other_sales_tax),2),
                                             'transactionsourcedesc': 'Secondary',
                                             'transagreementagreementdate': agreement_detail.agreementagreementdate ,
                                             'transagreementauthority': agreement_detail.agreementauthority,
                                             'transagreementclosedflag_id': '901',
                                             'transactionstatus': '905',
                                             'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                                             'transcustomercompany': agreement_detail.customercompany,
                                             'transagreementddstatus_id': agreement_detail.agreementddstatus_id,
                                             'transagreementdefname': 'Lease Agreement',
                                             # 'transcustomercompany': customers.customernumber,
                                             'transddpayment': '1',
                                             # 'transgrosspayment':,
                                             'transnetpaymentcapital' : Decimal(re.sub(',', '', '0.00')),
                                             'transnetpaymentinterest' : round(Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee)),2),
                                             }
                        if agreement_detail.agreement_stage == 4:
                            go_account_transaction_summary.objects.filter(agreementnumber=agreement_id, transactionstatus='905').update(transactionstatus='901')

                        if go_id.secondary_flag == 1:
                            ats_secondary_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee))

                            if agreement_detail.agreementdefname == 'Hire Purchase':
                                ats_secondary_rec['transagreementdefname'] = 'Hire Purchase'
                                ats_secondary_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee))

                            go_account_transaction_summary(**ats_secondary_rec).save()
                            atd_secondary_rentals_rec = {'go_id': go_id,
                                                         'agreementnumber': agreement_id,
                                                         # 'transtypeid': '0',
                                                         'transactiondate': agreement_detail.agreementresidualdate + relativedelta(months=+(i+1)),
                                                         'transactionsourceid': 'GO3',
                                                         # 'transtypedesc': 'Documentation Fee',
                                                         'transflag': 'Sec',
                                                         'transfallendue': '0',
                                                         'transnetpayment': Decimal(re.sub(',', '', instalmentnet)),
                                                         'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                                                         'transpayprointerest': Decimal(re.sub(',', '', instalmentnet)),
                                                         }


                            go_account_transaction_detail(**atd_secondary_rentals_rec).save()

                            atd_secondary_risk_rec = {'go_id': go_id,
                                                      'agreementnumber': agreement_id,
                                                      'transtypeid': '3',
                                                      'transactiondate': agreement_detail.agreementresidualdate + relativedelta(months=+(i+1)),
                                                      'transactionsourceid': 'GO3',
                                                      'transtypedesc': 'Risk Fee',
                                                      'transflag': 'SFn',
                                                      'transfallendue': '0',
                                                      'transnetpayment': Decimal(re.sub(',', '', riskfee)),
                                                      'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                                                      'transpayprointerest': Decimal(re.sub(',', '', riskfee)),
                                                      }
                            if go_id.risk_flag == 1:
                                go_account_transaction_detail(**atd_secondary_risk_rec).save()
                        if go_id.broker_id == 2:
                            go_account_transaction_detail(**atd_secondary_rentals_rec).save()

                    return redirect('core_agreement_crud:agreement_management_tab4', agreement_id)

        except Exception as e:
            error = '{} {}'.format(e, traceback.format_exc())

    context['error'] = error
    context['errors'] = errors
    context['values'] = values
    context['go_id'] = go_id
    context['datacash_request'] = request.GET.get('datacash_request')

    return render(request, template, context)


@login_required(login_url='signin')
def agreement_management_tab4(request, agreement_id):

    stage = "4"
    errors = {}
    # context = {'agreement_id': agreement_id}
    template = 'core_agreement_crud/agreement_management_tab4.html'

    context = {'agreement_id': agreement_id, 'transaction_id': request.GET.get('transaction_id'),
               'trans_detail_id': request.GET.get('trans_detail_id')}

    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)

    # Core Querysets
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    context['agreement_detail'] = agreement_detail

    agreement_customer = go_customers.objects.get(customernumber=agreement_detail.agreementcustomernumber)
    config = client_configuration.objects.get(client_id="NWCF")
    context['agreement_customer'] = agreement_customer

    context['username'] = request.user.username

    account_detail = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id) \
        .order_by('transtypedesc', )
    context['account_detail'] = account_detail
    account_summary = go_account_transaction_summary.objects.filter(agreementnumber=agreement_id).order_by('transactiondate', 'transactionsourceid')
    context['account_summary'] = account_summary
    account_detail_fees = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                                              transactionsourceid='GO1',
                                                                              transtypeid__isnull=False) \
        .order_by('transtypedesc', )
    context['account_detail_fees'] = account_detail_fees

    try:
        transaction_summary_extract = go_account_transaction_summary.objects.filter(agreementnumber=agreement_id,
                                                                                    transactionbatch_id__contains='GO')
        context['transaction_summary_extract_count'] = transaction_summary_extract.count()
        transition = transition_log.objects.filter(agreementnumber=agreement_id)
        context['transition_count'] = transition.count()

    except:
        error = None

    # Agreement Type
    if agreement_detail.agreementdefname != 'Hire Purchase' and agreement_detail.agreementdefname != 'Management Fee':
        agreement_type = 'Lease'
        sales_tax_rate = config.other_sales_tax
    else:
        agreement_type = 'HP'
        sales_tax_rate = 1.0

    # Agreement Payable Net of VAT
    try:
        agreement_payable_net = agreement_detail.agreementoriginalprincipal + agreement_detail.agreementcharges
    except:
        agreement_payable_net = 0

    # Add in Fees if they exist
    try:
        agreement_fees_net = account_detail_fees.aggregate(Sum('transnetpayment'))
        if agreement_fees_net is not None:
            agreement_payable_net += agreement_fees_net["transnetpayment__sum"]
    except:
        agreement_fees_net = None
        agreement_payable_net = 0
        pass

    # Agreement Payable Gross of VAT
    agreement_payable_gross = (agreement_payable_net * decimal.Decimal(sales_tax_rate))

    # Agreement Instalment Gross
    agreement_instalment_gross = agreement_detail.agreementinstalmentnet
    if agreement_detail.agreementinstalmentvat is not None:
        agreement_instalment_gross += agreement_detail.agreementinstalmentvat
    if agreement_detail.agreementinstalmentins is not None:
        agreement_instalment_gross += agreement_detail.agreementinstalmentins

    # Sundry Items
    settlement_figure_queryset = account_summary.aggregate(Sum('transgrosspayment'))
    settlement_figure_vat  = settlement_figure_queryset['transgrosspayment__sum']

    settlement_figure_queryset = account_summary.aggregate(Sum('transnetpayment'))
    settlement_figure_net = settlement_figure_queryset['transnetpayment__sum']

    # if agreement_type == 'Lease':
    #     settlement_figure_vat = settlement_figure * decimal.Decimal(sales_tax_rate)
    # else:
    #     settlement_figure_vat = settlement_figure * decimal.Decimal(sales_tax_rate)

    first_rental_date = agreement_detail.agreementfirstpaymentdate

    # get Number of Document Fees
    try:
        doc_fee_count = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                                     transactionsourceid__in=['SP1', 'GO1'],
                                                                     transactiondate__lt=first_rental_date) \
            .count()
    except:
        doc_fee_count = 0

    # get Number of Primaries
    try:
        primary_count = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                                     transactionsourceid__in=['SP1', 'GO1'],
                                                                     transtypeid__isnull=True,
                                                                     transactiondate__gte=first_rental_date) \
            .count()
    except:
        primary_count = 0

    # get Number of Secondaries
    try:
        secondary_count = account_summary.filter(transactionsourceid__in=['SP2', 'SP3', 'GO3']).count()
    except:
        secondary_count = 0

    row_index = 0
    for row in account_summary:
        if row.transactionsourceid in ['GO1', 'GO2', 'GO3', 'SP1', 'SP2', 'SP3']:
            if row.transactiondate >= agreement_detail.agreementfirstpaymentdate:
                row_index += 1
        row.row_index = row_index

    # Add Gross of Vat to account detail queryset
    for row in account_detail:
        row.transvatpayment = row.transnetpayment * decimal.Decimal(0.2)

    if request.method == 'POST':
        try:
            _process = True
            _redirect = True

            if request.POST.get('reopen') == 'true':
                reopen_function(request, agreement_id)
                _process = False

            # If we are consolidating, check than none of the
            # consolidating agreements are already in a batch.
            if go_id.consolidation_info:
                consol_agreements_in_batch = []
                consol_agreements = go_id.consolidation_info.split("::")
                for aid in consol_agreements:
                    dd_filter = DrawDown.objects.filter(status='OPEN', agreement_id=aid)
                    if dd_filter.exists():
                        _process = False
                        _redirect = False
                        for row in dd_filter:
                            consol_agreements_in_batch.append({'batch_header': row.batch_header.reference,
                                                               'due_date': row.due_date.strftime("%d/%m/%Y"),
                                                               'user': row.user.username, 'agreement_id': aid})
                if len(consol_agreements_in_batch):
                    context['console_batch_conflicts'] = consol_agreements_in_batch

            if _process:
                go_agreement_querydetail.objects.filter(go_id=go_id).update(agreement_stage=stage, agreementclosedflag='901')
                go_account_transaction_summary.objects.filter(agreementnumber=agreement_id,
                                                              transactionstatus='905').update(transactionstatus='901')
                if go_id.consolidation_info:
                    for agreement in go_id.consolidation_info.split('::'):
                        go_agreement_index.objects.filter(agreement_id=agreement).update(consolidation_info='Consolidated into ' + str(go_id.agreement_id) + ' on ' + datetime.datetime.today().strftime('%Y-%m-%d'))
                        consolidation_function(request, agreement)

                    go_agreement_index.objects.filter(agreement_id=go_id).update(
                        consolidation_info='Consolidated from ' + go_id.consolidation_info.replace('::',',') + ' on ' + (datetime.datetime.today().strftime('%Y-%m-%d')))

                return redirect("core_agreement_crud:AgreementEnquiryList")

            if _redirect:
                url = reverse('core_agreement_crud:agreement_management_tab4', args=[agreement_id])
                return redirect(url + '?change_profile=1')

        except Exception as e:
            context['error'] = e

    context['errors'] = errors
    context['values'] = request.POST

    context.update({
        'change_profile': request.GET.get('change_profile'),
        'batch_error': request.GET.get('batch_error'),
        'agreement_payable_net': agreement_payable_net,
        'agreement_payable_gross': agreement_payable_gross,
        'agreement_instalment_gross': agreement_instalment_gross,
        'agreement_fees_net': agreement_fees_net,
        # 'bacs_audit': bacs_audit,
        'account_detail': account_detail,
        'account_summary': account_summary,
        'settlement_figure_net': settlement_figure_net,
        'settlement_figure_vat': settlement_figure_vat,
        'agreement_type': agreement_type,
        'doc_fee_count': doc_fee_count,
        'primary_count': primary_count,
        'secondary_count': secondary_count,
        'go_id' : go_id,
        'show_sentinel_button': True,
        'today': datetime.datetime.now().strftime("%Y-%m-%d")
        # ,'agreement_regulated_flag': agreement_regulated_flag}
    })

    if DrawDown.objects.filter(status='OPEN', agreement_id=agreement_id).exists():
        context['show_sentinel_button'] = False
        context['is_in_batch'] = True

    return render(request, template, context)


@login_required(login_url='signin')
def agreement_management_tab5(request, agreement_id):

    stage = "5"
    errors = {}
    context = {'agreement_id': agreement_id}
    template = 'core_agreement_crud/agreement_management_tab5.html'

    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)

    # Core Querysets
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    context['agreement_detail'] = agreement_detail

    agreement_customer = go_customers.objects.get(customernumber=agreement_detail.agreementcustomernumber)
    config = client_configuration.objects.get(client_id="NWCF")
    context['agreement_customer'] = agreement_customer

    context['username'] = request.user.username

    account_detail = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id) \
        .order_by('transtypedesc', )
    context['account_detail'] = account_detail
    account_summary = go_account_transaction_summary.objects.filter(agreementnumber=agreement_id)
    context['account_summary'] = account_summary
    account_detail_fees = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                                              transactionsourceid='GO1',
                                                                              transtypeid__isnull=False) \
        .order_by('transtypedesc', )
    context['account_detail_fees'] = account_detail_fees

    # Agreement Type
    if agreement_detail.agreementdefname != 'Hire Purchase' and agreement_detail.agreementdefname != 'Management Fee':
        agreement_type = 'Lease'
        sales_tax_rate = config.other_sales_tax
    else:
        agreement_type = 'HP'
        sales_tax_rate = 1.0

    # Agreement Payable Net of VAT
    try:
        agreement_payable_net = agreement_detail.agreementoriginalprincipal + agreement_detail.agreementcharges
    except:
        agreement_payable_net = 0

    # Add in Fees if they exist
    try:
        agreement_fees_net = account_detail_fees.aggregate(Sum('transnetpayment'))
        if agreement_fees_net is not None:
            agreement_payable_net += agreement_fees_net["transnetpayment__sum"]
    except:
        agreement_fees_net = None
        agreement_payable_net = 0
        pass

    # Agreement Payable Gross of VAT
    agreement_payable_gross = (agreement_payable_net * decimal.Decimal(sales_tax_rate))

    # Agreement Instalment Gross
    agreement_instalment_gross = agreement_detail.agreementinstalmentnet
    if agreement_detail.agreementinstalmentvat is not None:
        agreement_instalment_gross += agreement_detail.agreementinstalmentvat
    if agreement_detail.agreementinstalmentins is not None:
        agreement_instalment_gross += agreement_detail.agreementinstalmentins

    # Sundry Items
    settlement_figure_queryset = account_summary.aggregate(Sum('transnetpayment'))
    settlement_figure = settlement_figure_queryset['transnetpayment__sum']
    if settlement_figure is None: settlement_figure_vat = 0
    else:
        if agreement_type == 'Lease':
            settlement_figure_vat = settlement_figure * decimal.Decimal(sales_tax_rate)
        else:
            settlement_figure_vat = settlement_figure * decimal.Decimal(sales_tax_rate)

    first_rental_date = agreement_detail.agreementfirstpaymentdate

    # get Number of Document Fees
    try:
        doc_fee_count = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                                            transactionsourceid='GO1',
                                                                            transactiondate__lt=first_rental_date) \
            .count()
    except:
        doc_fee_count = 0

    # get Number of Primaries
    try:
        primary_count = go_agreement_index.term

    except:
        primary_count = 0

    # get Number of Secondaries
    try:
        secondary_count = account_summary.filter(transactionsourceid__in=['GO2', 'GO3']).count()
    except:
        secondary_count = 0

    # Add Gross of Vat to account summary queryset
    row_index = 0
    for row in account_summary:
        # if row.transactionsourceid in ['GO8','GO9', 'SP9'] and row.transvatpayment is not None:
        if row.transactionsourceid in ['GO8', 'GO9', 'SP9']:
            # row.transgrosspayment = row.transnetpayment + row.transvatpayment
            row.transgrosspayment = row.transnetpayment * decimal.Decimal(sales_tax_rate)
        else:
            row.transgrosspayment = row.transnetpayment * decimal.Decimal(sales_tax_rate)
        if row.transactionsourceid in ['GO1', 'GO2', 'GO3', 'SP1', 'SP2', 'SP3']:
            if row.transactiondate >= agreement_detail.agreementfirstpaymentdate:
                row_index += 1
        row.row_index = row_index
    # Add Gross of Vat to account detail queryset
    for row in account_detail:
        row.transvatpayment = row.transnetpayment * decimal.Decimal(0.2)

    if request.method == 'POST':
        try:

            request.method = 'GET'
            return agreement_management_tab5(request, agreement_id)

        except Exception as e:
            context['error'] = e

    context['errors'] = errors
    context['values'] = request.POST
    go_agreement_querydetail.objects.filter(go_id=go_id).update(agreement_stage=stage)

    context.update({
        'agreement_payable_net': agreement_payable_net,
        'agreement_payable_gross': agreement_payable_gross,
        'agreement_instalment_gross': agreement_instalment_gross,
        'agreement_fees_net': agreement_fees_net,
        # 'bacs_audit': bacs_audit,
        'account_detail': account_detail,
        'account_summary': account_summary,
        'settlement_figure': settlement_figure,
        'settlement_figure_vat': settlement_figure_vat,
        'agreement_type': agreement_type,
        'doc_fee_count': doc_fee_count,
        'primary_count': primary_count,
        'secondary_count': secondary_count
        # ,'agreement_regulated_flag': agreement_regulated_flag}
    })

    return render(request, template, context)


@login_required(login_url='signin')
def archive_agreement(request, agreement_id):
    if request.method == 'POST':
        archive_agreement_function(request, agreement_id)
        cancel_ddi_with_datacash(agreement_id, user=request.user)
        # print('test')

    return redirect('core_agreement_crud:AgreementEnquiryList')


@login_required(login_url='signin')
def unarchive_agreement(request, agreement_id):
    if request.method == 'POST':
        unarchive_agreement_function(request, agreement_id)
        # cancel_ddi_with_datacash(agreement_id, user=None)

    return redirect('core_agreement_crud:AgreementEnquiryList')


@login_required(login_url='signin')
def refund(request, agreement_id):

    if request.method == 'POST':
        refund_function(request, agreement_id)

    return redirect('core_agreement_crud:agreement_management_tab4', agreement_id)






