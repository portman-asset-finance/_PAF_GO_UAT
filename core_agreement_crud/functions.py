import math
import re
import decimal
import datetime
from django.db.models import Sum
from datetime import timedelta
from dateutil.relativedelta import *
from decimal import Decimal
from datetime import datetime

from core_direct_debits.functions import cancel_ddi_with_datacash, create_ddi_with_datacash, generate_dd_reference

from core_dd_drawdowns.models import DDHistory

from anchorimport.models import AnchorimportAccountTransactionSummary

from core.models import holiday_dates

from core.functions_go_id_selector import client_configuration

from .models import go_customers, go_agreement_querydetail, go_agreements, \
                    go_account_transaction_detail, go_account_transaction_summary, go_agreement_index

from core_agreement_editor.models import go_editor_history

from core_agreement_editor.models import go_settlement


def get_next_due_date(agreement_id):

    due_date = None

    try:
        go_id_obj = go_agreement_index.objects.get(agreement_id=agreement_id)
        filter_obj = {
            'go_id': go_id_obj,
            'transactiondate__gt': datetime.now(),
            'transagreementclosedflag': '901'
        }
        filtered_recs = go_account_transaction_summary.objects.filter(**filter_obj).order_by('transactiondate')
        if filtered_recs.count() > 0:
            due_date = filtered_recs[:1][0].transactiondate#.strftime("%Y-%m-%d")
            return due_date
    except Exception as e:
        due_date = None

    try:
        filter_obj = {
            'agreementnumber': agreement_id,
            'transactiondate__gt': datetime.now(),
            'transagreementclosedflag': '901'
        }
        filtered_recs = AnchorimportAccountTransactionSummary.objects.filter(**filter_obj).order_by('transactiondate')
        if filtered_recs.count() > 0:
            due_date = filtered_recs[:1][0].transactiondate
            return due_date
    except Exception as e:
        due_date = None

    return due_date


def get_holidays(from_date=datetime.today(), max_days_ahead=90):

    filter_obj = {
        'holiday_date__gte': from_date,
        'holiday_date__lte': from_date + timedelta(days=max_days_ahead)
    }

    recs = []
    for rec in holiday_dates.objects.filter(**filter_obj):
        recs.append('{}'.format(rec.holiday_date))

    return recs


def validate_tab1(post_data, errors_obj):
    """
    Validates tab1 post data
    :return:
    """

    error_count = 0

    if not post_data.get('agreement_type'):
        error_count += 1
        errors_obj['agreement_type'] = 'Agreement Type Required'

    # if not post_data.get('profile_type'):
    #    error_count += 1
    #    errors_obj['profile_type'] = 'Profile Type Required'

    if not post_data.get('broker_type'):
        error_count += 1
        errors_obj['broker_type'] = 'Broker Required'
    go_filter = go_account_transaction_summary.objects.filter(agreementnumber=post_data.get('agreement_id'))
    if go_filter.count() == 0:
        if not post_data.get('funder_code'):
            error_count += 1
            errors_obj['funder_code'] = 'Funder Required'

    if not post_data.get('company_name'):
        error_count += 1
        errors_obj['company_name'] = 'Company Name Required'

    if not post_data.get('agreement_id'):
        error_count += 1
        errors_obj['agreement_id'] = 'Agreement ID Required'

    if not post_data.get('customeraddress1'):
        error_count += 1
        errors_obj['customeraddress1'] = 'Address Line 1 Required'

    if not post_data.get('customeraddress2'):
        error_count += 1
        errors_obj['customeraddress2'] = 'Address Line 2 Required'

    if not post_data.get('customerpostcode'):
        error_count += 1
        errors_obj['customerpostcode'] = 'Customer Postcode Required'

    # if not post_data.get('customercontact'):
    #     error_count += 1
    #     errors_obj['customercontact'] = 'Contact Name Required'

    if not post_data.get('customerfirstname'):
        error_count += 1
        errors_obj['customerfirstname'] = 'First Name Required'

    if not post_data.get('customersurname'):
        error_count += 1
        errors_obj['customersurname'] = 'Surname Required'

    if not post_data.get('customeremail'):
        error_count += 1
        errors_obj['customeremail'] = 'Email Required'

    if not post_data.get('agreementauthority'):
        error_count += 1
        errors_obj['agreementauthority'] = 'Account Manager Required'

    if not post_data.get('customermobilenumber') and not post_data.get('customerphonenumber'):
        errors_obj['customermobilenumber'] = 'Mobile or Phone Required'
        errors_obj['customerphonenumber']  = 'Mobile or Phone Required'
        error_count += 1

    if post_data.get('customermobilenumber'):
        if not validate_mobile_number(post_data['customermobilenumber'], errors_obj, 'customermobilenumber'):
            error_count += 1

    if post_data.get('customerphonenumber'):
        if not validate_phone_number(post_data['customerphonenumber'], errors_obj, 'customerphonenumber'):
            error_count += 1

    if post_data.get('customeremail'):
        if not validate_email_addr(post_data['customeremail'], errors_obj, 'customeremail'):
            error_count += 1
    else:
        error_count += 1
        errors_obj['customeremail'] = 'Email Address Required'

    if error_count:
        return False

    return True


def validate_agreement_number(aid, err_obj, err_key, broker_type, current_agreement_id=False):
    """
    Validates a given agreement number

    """

    # Min length: 4
    # Max length: 5
    # If broker add 99

    min_length = 4
    max_length = 4

    if broker_type == 'Broker':
        max_length = 5
        min_length = 5
        if aid[:1] != '9':
            err_obj[err_key] = 'Agreement number must start with a 9'
            return

    if len(aid) < min_length:
        err_obj[err_key] = 'Min length must be {}'.format(min_length)
        return

    if len(aid) > max_length:
        err_obj[err_key] = 'Max length must be {}'.format(max_length)
        return

    if current_agreement_id != aid:
        if go_agreement_index.objects.filter(agreement_id=aid).exists():
            err_obj[err_key] = 'Already exists'
            return
        if go_agreement_querydetail.objects.filter(agreementnumber=aid).exists():
            err_obj[err_key] = 'Already exists'
            return
        if go_agreements.objects.filter(agreementnumber=aid).exists():
            err_obj[err_key] = 'Already exists'
            return

    if not re.search('^\\d+$', aid):
        err_obj[err_key] = 'Agreement number must be digits only'
        return

    return True

        # if val_rec.prepend:
        #     if not re.search(re.compile('^{}'.format(val_rec.prepend)), aid):
        #         err_obj[err_key] = 'Agreement number must start with {}'.format(val_rec.prepend)
        #         return
        #     aid = re.sub(re.compile(r'^{}'.format(val_rec.prepend)), '', aid)
        #
        # if val_rec.append:
        #     if not re.search(re.compile('{}$'.format(val_rec.append)), aid):
        #         err_obj[err_key] = 'Agreement number must end with {}'.format(val_rec.append)
        #         return
        #     aid = re.sub(re.compile(r'{}$'.format(val_rec.append)), '', aid)
        #
        # if not val_rec.allow_digits:
        #     if re.search(r'\d+', aid):
        #         err_obj[err_key] = 'Agreement number must not contain digits'
        #         return
        #
        # if not val_rec.allow_letters:
        #     if re.search(r'[a-zA-Z]+', aid):
        #         err_obj[err_key] = 'Agreement number must not contain letters'
        #         return
        #
        # if not val_rec.allow_characters:
        #     if re.search(r'\W+', aid):
        #         err_obj[err_key] = 'Agreement number must not contain any special characters'
        #         return

    return True


def validate_mobile_number(mobile, err_obj, err_key):
    """
    Validates a given mobile number

    """

    mobile = re.sub(re.compile('\s+'), '', mobile)

    if not mobile:
        err_obj[err_key] = 'Mobile Number Required'
        return

    if len(mobile) > 11:
        err_obj[err_key] = 'Max 11 digits long.'
        return

    if len(mobile) < 10:
        err_obj[err_key] = 'Min 10 digits long.'
        return

    # if mobile[:2] != '07':
    #     err_obj[err_key] = 'Mobile Number must start with a 07'
    #     return

    if not re.search(r'\d+', mobile):
        err_key[err_key] = 'Mobile Number must contain digits only'

    return True


def validate_phone_number(phone, err_obj, err_key):
    """
    Validates a given mobile number

    """

    phone = re.sub(re.compile('\s+'), '', phone)

    if not phone:
        err_obj[err_key] = 'Phone Number Required'
        return

    if len(phone) > 11:
        err_obj[err_key] = 'Max 11 digits long.'
        return

    if len(phone) < 10:
        err_obj[err_key] = 'Min 10 digits long.'
        return

    if not re.search(r'\d+', phone):
        err_key[err_key] = 'Phone Number must contain digits only'

    return True


def validate_email_addr(email, err_obj, err_key):
    """
    Validate a given email address

    """

    if not email:
        err_obj[err_key] = 'Email Address Required'
        return

    if not re.match('[^@]+@[^@]+\.[^@]+', email):
        err_obj[err_key] = 'Invalid Email Address'
        return

    return True

def validate_currency(currency):
    """
    Validates that the value given is a Decimal
    :param currency:
    :return: bool
    """
    if not currency:
        return False

    if not re.search('^\d+$', currency):
        return False

    if not re.search('^0', currency):
        return False

    try:
        decimal.Decimal(currency)
    except:
        return False

    return True

def validate_number(number):
    """
    Validates that the value given is a valid number
    :param number:
    :return: bool
    """
    if not number:
        return False

    if not re.search('^\d+$', number):
        return False

    if not re.search('^0', number):
        return False

    try:
        int(number)
    except:
        return False

    return True

# def validate_principal(number):
#     """
#     Validates that the value given is a valid number
#     :param number:
#     :return: bool
#     """
#     if not number:
#         return False
#
#     if not re.search('^\d+$', number):
#         return False
#
#     if not re.search('^0', number):
#         return False
#
#     try:
#         int(number)
#     except:
#         return False
#
#     return True

def validate_date(date, format="%Y-%m-%d"):
    """
    Validates that the value given is a valid date
    :param date:
    :return:
    """
    try:
        datetime.strptime(date, format)
    except:
        return False

    return True

def generate_customer_number():

    client_config = client_configuration.objects.get(client_id='NWCF')

    customer_number_iteration = client_config.customer_number_iteration

    next_customer_number_iteration = int(customer_number_iteration) + 1

    while True:

        next_customer_number = '{}{}'.format(client_config.prefix, next_customer_number_iteration)

        if go_customers.objects.filter(customernumber=next_customer_number).count() == 0:

            client_config.customer_number_iteration = next_customer_number_iteration
            client_config.save()

            return next_customer_number

        next_customer_number_iteration += 1


def recalculate_fees(agreement_id):
    pass


def recalculate_function(agreement_id):

    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    riskfee = str(go_id.agreement_risk_fee)
    bamffee = str(go_id.agreement_bamf_fee)
    docfee = str(go_id.agreement_doc_fee)
    principal = str(agreement_detail.agreementoriginalprincipal)
    instalmentnet = str(agreement_detail.agreementinstalmentnet)
    go_account_transaction_summary.objects.filter(go_id=go_id, transactionsourceid='GO1').delete()
    go_account_transaction_summary.objects.filter(go_id=go_id, transactionsourceid='GO3').delete()
    go_account_transaction_detail.objects.filter(go_id=go_id, transactionsourceid='GO1').delete()
    go_account_transaction_detail.objects.filter(go_id=go_id, transactionsourceid='GO3').delete()
    config = client_configuration.objects.get(client_id='NWCF')

    if Decimal(agreement_detail.agreement_stage) >= 3:
    # Risk Fee
        instalmentnet2 = (agreement_detail.agreementinstalmentnet)

        if agreement_detail.agreementinstalmentnet < 500:
            risk_fee = '0'
        if instalmentnet2 >= 500:
            risk_fee = '100'
        if instalmentnet2 > 2000:
            risk_fee = '200'
        if instalmentnet2 > 3000:
            risk_fee = '300'
        # if go_id.prof#ile_id in (3, 4):
        #     risk_fee = '0'
        if go_id.risk_flag == 0:
            risk_fee = '0'
        # risk_fee = '100'
        riskfeecorrection = go_agreement_index.objects.get(agreement_id=agreement_id)
        riskfeecorrection.agreement_risk_fee = Decimal(risk_fee)
        riskfeecorrection.save();

        if agreement_detail.agreementdefname == 'Hire Purchase':
            risk_fee = str(Decimal(risk_fee))
        else : risk_fee = str(Decimal(risk_fee)/Decimal(config.other_sales_tax))

        riskfee = risk_fee

        print(riskfee)

        # go_agreement_querydetail.objects.filter(go_id=go_id).update(agreement_stage=stage)
        docfee_rec = {'go_id': go_id,
                      'agreementnumber': go_id,
                      'transtypeid' : '1',
                      'transactiondate': agreement_detail.agreementupfrontdate,
                      'transactionsourceid' : 'GO1',
                      'transtypedesc' : 'Documentation Fee',
                      'transflag' : 'Fee',
                      'transfallendue' : '1',
                      'transnetpayment': docfee,
                      'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                      'transpayprointerest': Decimal(re.sub(',', '', docfee)),
                      }

        ats_docfee_rec = {'go_id': go_id,
                          'agreementnumber': go_id,
                          'transtypeid': '0',
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
                          'transagreementclosedflag_id' : '901',
                          'transactionstatus': '901',
                          'transagreementcustomernumber' : agreement_detail.agreementcustomernumber,
                          'transagreementddstatus_id' : agreement_detail.agreementddstatus_id,
                          'transagreementdefname' : 'Lease Agreement',
                          'transcustomercompany': agreement_detail.customercompany,
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

        if go_id.broker_id == 2:

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
                               'transtypeid': '0',
                               'transactiondate': agreement_detail.agreementupfrontdate + timedelta(seconds=1),
                               'transactionsourceid': 'GO1',
                               'transtypedesc': '',
                               'transflag': '',
                               'transfallendue': '0',
                               'transnetpayment': Decimal(re.sub(',', '', instalmentnet)),
                               'transgrosspayment': round(Decimal(re.sub(',', '', instalmentnet))*Decimal(config.other_sales_tax), 2),
                               'transactionsourcedesc': 'Primary',
                               'transagreementagreementdate': agreement_detail.agreementagreementdate,
                               'transagreementauthority': agreement_detail.agreementauthority,
                               'transagreementclosedflag_id': '901',
                               'transactionstatus': '901',
                               'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                               'transagreementddstatus_id': agreement_detail.agreementddstatus_id,
                               'transagreementdefname': 'Lease Agreement',
                               'transcustomercompany': agreement_detail.customercompany,
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
                               'transnetpayment': Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', str(riskfee))),
                               'transgrosspayment': round((Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', str(riskfee))))*Decimal(config.other_sales_tax), 2),
                               'transactionsourcedesc' : 'Primary',
                               'transagreementagreementdate': agreement_detail.agreementagreementdate,
                               'transagreementauthority': agreement_detail.agreementauthority,
                               'transagreementclosedflag_id': '901',
                               'transactionstatus': '901',
                               'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                               'transagreementddstatus_id': agreement_detail.agreementddstatus_id,
                               'transagreementdefname': 'Lease Agreement',
                               'transcustomercompany': agreement_detail.customercompany,
                               'transddpayment': '1',
                               # 'transgrosspayment':,
                               'transnetpaymentinterest': (go_id.term - i) * Decimal(multiplier2) + Decimal(re.sub(',', '', str(riskfee))),
                               'transnetpaymentcapital': Decimal(re.sub(',', '', instalmentnet))-(go_id.term - i) * Decimal(multiplier2),
                               }

            if agreement_detail.agreementdefname == 'Hire Purchase':
                ats_rentals_rec['transagreementdefname'] = 'Hire Purchase'
                ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                    re.sub(',', '', riskfee))

            if go_id.broker_id == 1:
                if i > 0 and (i + 1) % 6 == 0 and go_id.bamf_flag == 1 and go_id.risk_flag == 1:
                    ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                        re.sub(',', '', riskfee)) + Decimal(
                        re.sub(',', '', str(config.bamf_fee_amount_net)))
                    ats_rentals_rec['transnetpaymentinterest'] = (go_id.term - i) * Decimal(multiplier2) + Decimal(re.sub(',', '', str(riskfee)))+ Decimal(
                        re.sub(',', '', str(config.bamf_fee_amount_net)))
                    ats_rentals_rec['transgrosspayment'] = round((Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                        re.sub(',', '', riskfee))) * Decimal(config.other_sales_tax) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_vat))), 2)
                    if agreement_detail.agreementdefname == 'Hire Purchase':
                        ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                            re.sub(',', '', riskfee)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))
            else:
                if i > 0 and (i + 1) % 12 == 0:
                    ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                        re.sub(',', '', riskfee)) + Decimal(
                        re.sub(',', '', str(config.bamf_fee_amount_net)))
                    ats_rentals_rec['transnetpaymentinterest'] = (go_id.term - i) * Decimal(multiplier2) + Decimal(
                        re.sub(',', '', str(riskfee))) + Decimal(
                        re.sub(',', '', str(config.bamf_fee_amount_net)))
                    ats_rentals_rec['transgrosspayment'] = round((Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                        re.sub(',', '', riskfee))) * Decimal(config.other_sales_tax) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_vat))), 2)
                    if agreement_detail.agreementdefname == 'Hire Purchase':
                        ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                            re.sub(',', '', riskfee)) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_net)))

            if go_id.bamf_flag == 0 and go_id.risk_flag == 1:
                ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                    re.sub(',', '', riskfee))
                ats_rentals_rec['transnetpaymentinterest'] = (go_id.term - i) * Decimal(multiplier2) + Decimal(
                    re.sub(',', '', str(riskfee)))

                ats_rentals_rec['transgrosspayment'] = round((Decimal(re.sub(',', '', instalmentnet)) * Decimal(
                    config.other_sales_tax) + Decimal(re.sub(',', '', riskfee)) * Decimal(config.other_sales_tax)), 2)
                if agreement_detail.agreementdefname == 'Hire Purchase':
                    ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                        re.sub(',', '', riskfee))

            if go_id.broker_id == 1:
                if i > 0 and (i + 1) % 6 == 0 and go_id.bamf_flag == 1 and go_id.risk_flag == 0:
                    ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                        re.sub(',', '', str(config.bamf_fee_amount_net)))
                    ats_rentals_rec['transnetpaymentinterest'] = round((go_id.term - i) * Decimal(multiplier2) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_vat))), 2)
                    ats_rentals_rec['transgrosspayment'] = round(
                        (Decimal(re.sub(',', '', instalmentnet))) * Decimal(config.other_sales_tax) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_vat))), 2)
                    if agreement_detail.agreementdefname == 'Hire Purchase':
                        ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                            re.sub(',', '', str(config.bamf_fee_amount_net)))
            else:
                if i > 0 and (i + 1) % 12 == 0 :
                    ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                        re.sub(',', '', str(config.bamf_fee_amount_net)))
                    ats_rentals_rec['transnetpaymentinterest'] = (go_id.term - i) * Decimal(multiplier2) + Decimal(
                        re.sub(',', '', str(config.bamf_fee_amount_net)))
                    ats_rentals_rec['transgrosspayment'] = round(
                        (Decimal(re.sub(',', '', instalmentnet))) * Decimal(config.other_sales_tax) + Decimal(re.sub(',', '', str(config.bamf_fee_amount_vat))), 2)
                    if agreement_detail.agreementdefname == 'Hire Purchase':
                        ats_rentals_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(
                            re.sub(',', '', str(config.bamf_fee_amount_net)))

            if go_id.bamf_flag == 0 and go_id.risk_flag == 0 and go_id.broker_id == 1:
                ats_rentals_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet))
                ats_rentals_rec['transnetpaymentinterest'] = (go_id.term - i) * Decimal(multiplier2)
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
                               'transpayproprincipal': Decimal(re.sub(',', '', instalmentnet)) - (go_id.term - i) * Decimal(multiplier2),
                               'transpayprointerest': (go_id.term - i) * Decimal(multiplier2)
                                }
            if go_id.broker_id == 1:
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
            if go_id.amf_flag == 1:
                if i > 0 and (i+1) % 12 == 0:
                    atd_BAMF_rec = {'go_id': go_id,
                                    'agreementnumber': agreement_id,
                                    'transtypeid': '2',
                                    'transactiondate': agreement_detail.agreementfirstpaymentdate + relativedelta(months=+i),
                                    'transactionsourceid': 'GO1',
                                    'transtypedesc': 'Annual Management Fee',
                                    'transflag': 'Fee',
                                    'transfallendue': '0',
                                    'transnetpayment' : str(config.bamf_fee_amount_net),
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
                                 'transgrosspayment': round((Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee)))*Decimal(config.other_sales_tax), 2),
                                 'transactionsourcedesc': 'Secondary',
                                 'transagreementagreementdate': agreement_detail.agreementagreementdate,
                                 'transagreementauthority': agreement_detail.agreementauthority,
                                 'transagreementclosedflag_id': '901',
                                 'transactionstatus': '901',
                                 'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                                 'transagreementddstatus_id': agreement_detail.agreementddstatus_id,
                                 'transagreementdefname': 'Lease Agreement',
                                 'transcustomercompany': agreement_detail.customercompany,
                                 'transddpayment': '1',
                                 # 'transgrosspayment':,
                                 'transnetpaymentcapital' : Decimal(re.sub(',', '', '0.00')),
                                 'transnetpaymentinterest' : Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee)),
                                 }
            if go_id.secondary_flag == 1:
                ats_secondary_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet))

            # if go_id.profi#le_id == 4:
            #     ats_secondary_rec['transnetpayment'] = Decimal(re.sub(',', '', instalmentnet))

                if agreement_detail.agreementdefname == 'Hire Purchase':
                    ats_secondary_rec['transagreementdefname'] = 'Hire Purchase'
                    ats_secondary_rec['transgrosspayment'] = Decimal(re.sub(',', '', instalmentnet)) + Decimal(re.sub(',', '', riskfee))

                # account_transaction_detail(**ats_secondary_rec).save()
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


        #Charges
        chargecorrection = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
        chargecorrection.agreementcharges = Decimal(Interest)
        chargecorrection.save()


        #Risk Fee
        instalmentnet2=(agreement_detail.agreementinstalmentnet)

        if agreement_detail.agreementinstalmentnet < 500:
            risk_fee = '0'
        if instalmentnet2 > 500:
            risk_fee = '100'
        if instalmentnet2 > 2000:
            risk_fee = '200'
        if instalmentnet2 > 3000:
            risk_fee = '300'
        if go_id.risk_flag == 1:
            risk_fee = '0'
        if go_id.broker_id == 2:
            risk_fee = '0'
        # risk_fee = '100'

        if agreement_detail.agreementagreementtypeid.agreementdefid == 1:
            risk_fee = Decimal(risk_fee) / Decimal(config.other_sales_tax)

        riskfeecorrection = go_agreement_index.objects.get(agreement_id=agreement_id)
        riskfeecorrection.agreement_risk_fee=Decimal(risk_fee)
        riskfeecorrection.save()

        if go_id.bamf_flag == 0: Bamf = 0
        if go_id.bamf_flag == 1:  Bamf = config.bamf_fee_amount_net
        if go_id.broker_id == 1:
            a = (math.floor(go_id.term / 6))
        else:
            a = (math.floor(go_id.term / 12))
        b = Bamf * a
        c = go_id.term * round(go_id.agreement_risk_fee, 2)

        d = go_id.agreement_doc_fee
        totalFees = b + c + d


        totalfeescorrection = go_agreement_index.objects.get(agreement_id=agreement_id)
        totalfeescorrection.agreement_total_fees = Decimal(totalFees)
        totalfeescorrection.save()

        # PayableNet
        PayableNet = agreement_detail.agreementoriginalprincipal + Interest + totalFees
        # go_id.agreement_net

        payablenetcorrection = go_agreement_index.objects.get(agreement_id=agreement_id)
        payablenetcorrection.agreement_payable_net = Decimal(PayableNet)
        payablenetcorrection.save()

        #PayableGross
        # e=config.other_sales_tax
        PayableGross = PayableNet * Decimal(config.other_sales_tax)
        if agreement_detail.agreementdefname == 'Hire Purchase':
            PayableGross = PayableNet

        payablegrosscorrection = go_agreement_index.objects.get(agreement_id=agreement_id)

        payablegrosscorrection.agreement_payable_gross = Decimal(PayableGross)
        payablegrosscorrection.save()


def close_agreement_function(request, agreement_id):
    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    config = client_configuration.objects.get(client_id='NWCF')
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    instalmentnet = str(agreement_detail.agreementinstalmentnet)

    all_future_detail = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transnetpayment'))
    all_future_summary_principal = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentcapital'))
    all_future_summary_interest = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentinterest'))
    wip_element_value = all_future_detail["transnetpayment__sum"]
    wip_element_value_principal = all_future_summary_principal["transnetpaymentcapital__sum"]
    wip_element_value_interest = all_future_summary_interest["transnetpaymentinterest__sum"]

    all_future_detail_principal = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transpayproprincipal'))
    all_future_detail_interest = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transpayprointerest'))
    wip_element_value_pay_pro_principal = all_future_detail_principal["transpayproprincipal__sum"]
    wip_element_value_pay_pro_interest = all_future_detail_interest["transpayprointerest__sum"]


    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    customer = agreement_detail.customercompany

    cancel_ddi_with_datacash(agreement_id)

    close_rec = {'go_id': go_id,
                      'agreementnumber': go_id,
                      'transtypeid': '14',
                      'transactiondate': datetime.today(),
                      'transactionsourceid': 'GO8',
                      'transtypedesc': 'Close Agreement Payment',
                      'transflag': 'Col',
                      'transfallendue': '0',
                      'transnetpayment': -wip_element_value,
                      'transpayproprincipal': -wip_element_value_pay_pro_principal,
                      'transpayprointerest': -wip_element_value_pay_pro_interest,

                      }

    ats_close_rec = {'go_id': go_id,
                          'agreementnumber': go_id,
                          'transtypeid': '0',
                          'transactiondate': datetime.today(),
                          'transactionsourceid': 'GO8',
                          'transtypedesc': 'Close Agreement Payment',
                          'transflag': 'Col',
                          'transfallendue': '0',
                          'transnetpayment': -wip_element_value,
                          'transgrosspayment': round(-wip_element_value*Decimal(config.other_sales_tax), 2),
                          'transactionsourcedesc': 'HISTORY',
                          'transagreementagreementdate': datetime.today(),
                          'transagreementauthority': agreement_detail.agreementauthority,
                          'transagreementclosedflag_id': '902',
                          'transactionstatus': '902',
                          'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                          'transcustomercompany': agreement_detail.customercompany,
                          'transagreementddstatus_id': 'I',
                          'transagreementdefname': 'Agreement Finished',
                          'transddpayment': '0',
                          'transnetpaymentcapital': -wip_element_value_principal,
                          'transnetpaymentinterest': -wip_element_value_interest,
                          }

    agreements_close_rec = {'agreementstatus': 'CLOSED',
                                 'agreementautostatus': 'CLOSED(Settled)',
                                 'transagreementclosedflag_id': '902',
                                 'transactionstatus': '902',

                                 }
    go_agreements_index_close_rec = {'agreement_closed_reason': 'Agreement Settled',
                                          }

    go_agreement_index.objects.filter(go_id=go_id
                                      ).update(agreement_closed_reason='Agreement Settled')

    go_agreements.objects.filter(go_id=go_id
                                 ).update(agreementstatus='CLOSED',
                                          agreementautostatus='CLOSED(Settled)',
                                          agreementclosedflag_id='902')
    go_agreement_querydetail.objects.filter(go_id=go_id
                                            ).update(agreementstatus='CLOSED',
                                                     agreementautostatus='CLOSED(Settled)',
                                                     agreementclosedflag_id='902')
    go_agreement_index.objects.filter(go_id=go_id).update(agreement_origin_flag='GO')
    go_account_transaction_detail(**close_rec).save()
    go_account_transaction_summary(**ats_close_rec).save()

def consolidation_function(request, agreement):

    go_id = go_agreement_index.objects.get(agreement_id=agreement)
    config = client_configuration.objects.get(client_id='NWCF')
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement)
    instalmentnet = str(agreement_detail.agreementinstalmentnet)

    all_future_detail = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transnetpayment'))
    all_future_summary_principal = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentcapital'))
    all_future_summary_interest = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentinterest'))
    wip_element_value = all_future_detail["transnetpayment__sum"]
    wip_element_value_principal = all_future_summary_principal["transnetpaymentcapital__sum"]
    wip_element_value_interest = all_future_summary_interest["transnetpaymentinterest__sum"]

    all_future_detail_principal = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transpayproprincipal'))
    all_future_detail_interest = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transpayprointerest'))
    wip_element_value_pay_pro_principal = all_future_detail_principal["transpayproprincipal__sum"]
    wip_element_value_pay_pro_interest = all_future_detail_interest["transpayprointerest__sum"]

    if agreement_detail.agreementdefname == 'Hire Purchase':
        tax_rate = Decimal(config.other_sales_tax)
    tax_rate = Decimal(1)

    all_future_detail_interest = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentinterest'))
    wip_element_value_interest = all_future_detail_interest["transnetpaymentinterest__sum"]

    all_future_detail_capital = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentcapital'))
    wip_element_value_capital = all_future_detail_capital["transnetpaymentcapital__sum"]

    consolidation_rec = {'go_id': go_id,
                      'agreementnumber': go_id,
                      'transtypeid': '14',
                      'transactiondate': datetime.today(),
                      'transactionsourceid': 'GO8',
                      'transtypedesc': 'Consolidation Payment',
                      'transflag': 'Col',
                      'transfallendue': '0',
                      'transnetpayment': -round(wip_element_value,2),
                      'transpayproprincipal': -wip_element_value_pay_pro_principal,
                      'transpayprointerest': -wip_element_value_pay_pro_interest,
                      }

    ats_consolidation_rec = {'go_id': go_id,
                          'agreementnumber': go_id,
                          'transtypeid': '0',
                          'transactiondate': datetime.today(),
                          'transactionsourceid': 'GO8',
                          'transtypedesc': 'Consolidation Payment',
                          'transflag': 'Col',
                          'transfallendue': '0',
                          'transnetpayment': round(-wip_element_value, 2),
                          'transgrosspayment': round(-wip_element_value*tax_rate, 2),
                          'transactionsourcedesc': 'HISTORY',
                          'transagreementagreementdate': datetime.today(),
                          'transagreementauthority': agreement_detail.agreementauthority,
                          'transagreementclosedflag_id': '902',
                          'transactionstatus': '902',
                          'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                          'transcustomercompany': agreement_detail.customercompany,
                          'transagreementddstatus_id': 'I',
                          'transagreementdefname': 'Agreement Finished',
                          'transddpayment': '0',
                          'transnetpaymentcapital': -wip_element_value_capital,
                          'transnetpaymentinterest': -wip_element_value_interest,
                          }

    # go_agreement_querydetail.objects.filter(agreementnumber=agreement
    #                                   ).update(agreement_closed_reason='Consol.')
    go_agreements.objects.filter(go_id=go_id
                                 ).update(agreementstatus='CLOSED',
                                          agreementautostatus='CLOSED(Consolidated)',
                                          agreementclosedflag_id='902')
    go_agreement_querydetail.objects.filter(go_id=go_id
                                            ).update(agreementstatus='CLOSED',
                                                     agreementautostatus='CLOSED(Consolidated)',
                                                     agreementclosedflag_id='902',
                                                     closeddate=datetime.now())

    go_agreement_querydetail.objects.filter(agreementnumber=agreement).update(agreement_closed_reason='Consol.')
    go_account_transaction_summary.objects.filter(go_id=go_id).update(transagreementclosedflag_id='902')
    go_account_transaction_summary.objects.filter(go_id=go_id, transactiondate__gt=datetime.today()).update(transactionstatus='902')

    go_agreement_index.objects.filter(go_id=go_id).update(agreement_origin_flag='GO')


    go_account_transaction_detail(**consolidation_rec).save()
    go_account_transaction_summary(**ats_consolidation_rec).save()

    go_id.consolidated_date = datetime.now()
    go_id.save()

    return True


def move_consol_amount_function(request, agreement_id):

    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)

    agreements = request.POST.getlist('agreements[]')
    go_id.consolidation_info = "::".join(agreements)
    go_id.save()

    consolidations = ', '.join(agreements)

    all_future_detail = go_account_transaction_summary.objects.filter(agreementnumber__in=agreements)
    wip_element_value = all_future_detail.aggregate(Sum('transnetpaymentcapital'))["transnetpaymentcapital__sum"]

    data = {'consolidations': consolidations, 'number_of_consolidations': agreements,
            'total_principal': "{0:.2f}".format(wip_element_value or 0)}

    return data


def global_termination_function(request, agreement_id):
    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    instalmentnet = str(agreement_detail.agreementinstalmentnet)

    all_future_detail = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transnetpayment'))
    all_future_summary_principal = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentcapital'))
    all_future_summary_interest = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentinterest'))
    wip_element_value = all_future_detail["transnetpayment__sum"]

    all_future_detail_principal = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transpayproprincipal'))
    all_future_detail_interest = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transpayprointerest'))
    wip_element_value_pay_pro_principal = all_future_detail_principal["transpayproprincipal__sum"]
    wip_element_value_pay_pro_interest = all_future_detail_interest["transpayprointerest__sum"]

    all_future_detail_gross = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transgrosspayment'))
    wip_element_value_gross = all_future_detail_gross["transgrosspayment__sum"]

    all_future_detail_interest = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentinterest'))
    wip_element_value_interest = all_future_detail_interest["transnetpaymentinterest__sum"]

    all_future_detail_capital = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentcapital'))
    wip_element_value_capital = all_future_detail_capital["transnetpaymentcapital__sum"]

    go_agreement_index.objects.filter(go_id=go_id).update(agreement_origin_flag='GO')

    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    customer = agreement_detail.customercompany

    cancel_ddi_with_datacash(agreement_id)

    history_change_date = {'go_id': go_id,
                           'agreement_id': agreement_id,
                           'user': request.user,
                           'updated': datetime.now(),
                           'action': 'Globally Terminated',
                           # 'transaction': format(transaction_date,'%d/%m/%Y'),
                           'customercompany': customer,
                           }
    go_editor_history(**history_change_date).save()

    global_termination_rec = {'go_id': go_id,
                      'agreementnumber': go_id,
                      'transtypeid': '5',
                      'transactiondate': datetime.today(),
                      'transactionsourceid': 'GO8',
                      'transtypedesc': 'Write-off to bad debt',
                      'transflag': 'Col',
                      'transfallendue': '0',
                      'transnetpayment': -wip_element_value,
                      'transpayproprincipal': -wip_element_value_pay_pro_principal,
                      'transpayprointerest': -wip_element_value_pay_pro_interest,
                      }

    ats_global_termination_rec = {'go_id': go_id,
                          'agreementnumber': go_id,
                          'transtypeid': '5',
                          'transactiondate': datetime.today(),
                          'transactionsourceid': 'GO8',
                          'transtypedesc': 'Write-off to bad debt',
                          'transflag': 'Col',
                          'transfallendue': '0',
                          'transnetpayment': -wip_element_value,
                          'transgrosspayment': -wip_element_value_gross,
                          'transactionsourcedesc': 'HISTORY',
                          'transagreementagreementdate': datetime.today(),
                          'transagreementauthority': agreement_detail.agreementauthority,
                          'transagreementclosedflag_id': '902',
                          'transactionstatus': '902',
                          'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                          'transcustomercompany': agreement_detail.customercompany,
                          'transagreementddstatus_id': 'I',
                          'transagreementdefname': 'Agreement Finished',
                          'transddpayment': '0',
                          'transnetpaymentcapital': -wip_element_value_capital,
                          'transnetpaymentinterest': -wip_element_value_interest,
                          }

    agreements_global_termination_rec = {'agreementstatus': 'CLOSED',
                                 'agreementautostatus': 'CLOSED(Settled)',
                                 'transagreementclosedflag_id': '902',
                                 'transactionstatus': '902',
                                 }
    # go_agreements_index_global_termination_rec = {'agreement_closed_reason': 'Agreement Settled',
    #                                       }

    go_agreement_querydetail.objects.filter(agreementnumber=agreement_id
                                      ).update(agreement_closed_reason='Globalled')

    go_account_transaction_summary.objects.filter(go_id=go_id).update(transagreementclosedflag_id='902')
    go_account_transaction_summary.objects.filter(go_id=go_id, transactiondate__gt=datetime.today()).update(transactionstatus='902')

    go_agreements.objects.filter(go_id=go_id
                                 ).update(agreementstatus='CLOSED',
                                          agreementautostatus='CLOSED(Settled)',
                                          agreementclosedflag_id='902')
    go_agreement_querydetail.objects.filter(go_id=go_id
                                            ).update(agreementstatus='CLOSED',
                                                     agreementautostatus='CLOSED(Settled)',
                                                     agreementclosedflag_id='902',
                                                     closeddate=datetime.now())

    go_account_transaction_detail(**global_termination_rec).save()
    go_account_transaction_summary(**ats_global_termination_rec).save()
    go_id.agreement_origin_flag = 'GO'

    go_id.globalled_date = datetime.now()
    go_id.save()


def settlement_function(request, agreement_id):
    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    config = client_configuration.objects.get(client_id='NWCF')
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    instalmentnet = str(agreement_detail.agreementinstalmentnet)

    cancel_ddi_with_datacash(agreement_id)

    arrears_total_collected = request.POST.get('arrears_total_collected')
    arrears_total_adjustment1 = request.POST.get('arrears_total_adjustment1')
    if arrears_total_adjustment1 == 'None':
        arrears_total_adjustment1 = 'Write-off Doc Fee'
    arrears_total_adjustment2 = request.POST.get('arrears_total_adjustment2')
    if arrears_total_adjustment2 == 'None':
        arrears_total_adjustment2 = 'Write-off Principal'
    arrears_total_adjustment3 = request.POST.get('arrears_total_adjustment3')
    if arrears_total_adjustment3 == 'None':
        arrears_total_adjustment3 = 'Write-off Charges'
    arrears_total_adjustment4 = request.POST.get('arrears_total_adjustment4')
    if arrears_total_adjustment4 == 'None':
        arrears_total_adjustment4 = 'Write-off Risk-Fee'
    arrears_total_adjustment5 = request.POST.get('arrears_total_adjustment5')
    if arrears_total_adjustment5 == 'None':
        arrears_total_adjustment5 = 'Write-off BAMF'
    arrears_total_adjustment6 = request.POST.get('arrears_total_adjustment6')
    if arrears_total_adjustment6 == 'None':
        arrears_total_adjustment6 = 'Write-off Secondaries'


    collected1 = request.POST.get('collected1')
    collected2 = request.POST.get('collected2')
    collected3 = request.POST.get('collected3')
    collected4 = request.POST.get('collected4')
    collected5 = request.POST.get('collected5')
    collected6 = request.POST.get('collected6')

    adjustment1 = request.POST.get('adjustment1')
    adjustment2 = request.POST.get('adjustment2')
    adjustment3 = request.POST.get('adjustment3')
    adjustment4 = request.POST.get('adjustment4')
    adjustment5 = request.POST.get('adjustment5')
    adjustment6 = request.POST.get('adjustment6')

    all_future_detail = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transnetpayment'))
    all_future_summary_principal = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentcapital'))
    all_future_summary_interest = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transnetpaymentinterest'))
    wip_element_value = all_future_detail["transnetpayment__sum"]

    all_future_detail_principal = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transpayproprincipal'))
    all_future_detail_interest = go_account_transaction_detail.objects.filter(go_id=go_id).aggregate(Sum('transpayprointerest'))
    wip_element_value_pay_pro_principal = all_future_detail_principal["transpayproprincipal__sum"]
    wip_element_value_pay_pro_interest = all_future_detail_interest["transpayprointerest__sum"]


    all_future_detail_gross = go_account_transaction_summary.objects.filter(go_id=go_id).aggregate(Sum('transgrosspayment'))
    wip_element_value_gross = all_future_detail_gross["transgrosspayment__sum"]



    write_off_value = Decimal(wip_element_value_gross) - Decimal(arrears_total_collected)
    write_off_value_net = Decimal(wip_element_value) - (Decimal(arrears_total_collected))/Decimal(config.other_sales_tax)

    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    customer = agreement_detail.customercompany

    history_change_date = {'go_id': go_id,
                           'agreement_id': agreement_id,
                           'user': request.user,
                           'updated': datetime.now(),
                           'action': 'Settled',
                           # 'transaction': format(transaction_date,'%d/%m/%Y'),
                           'customercompany': customer
                               }
    go_editor_history(**history_change_date).save()



    if Decimal(collected1)> 0:
        doc_fee_rec = {'go_id': go_id,
                      'agreementnumber': go_id,
                      'transtypeid' : '1',
                      'transactiondate': datetime.today(),
                      'transactionsourceid' : 'GO8',
                      'transtypedesc' : 'Documentation Fee Payment',
                      'transflag' : 'Col',
                      'transfallendue' : '0',
                      'transnetpayment': -round(Decimal(collected1)/Decimal(config.other_sales_tax),2),
                      'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                      'transpayprointerest': -round(Decimal(collected1)/Decimal(config.other_sales_tax),2),
                      }
        go_account_transaction_detail(**doc_fee_rec).save()

    if Decimal(collected2) > 0:
        principal_rec = {'go_id': go_id,
                       'agreementnumber': go_id,
                       # 'transtypeid': '1',
                       'transactiondate': datetime.today(),
                       'transactionsourceid': 'GO8',
                       'transtypedesc': 'Principal Payment',
                       'transflag': 'Col',
                       'transfallendue': '0',
                       'transnetpayment': -round(Decimal(collected2)/Decimal(config.other_sales_tax),2),
                       'transpayproprincipal': -round(Decimal(collected2)/Decimal(config.other_sales_tax),2),
                       'transpayprointerest': Decimal(re.sub(',', '', '0.00')),
                       }
        go_account_transaction_detail(**principal_rec).save()

    if Decimal(collected3) > 0:
        charges_rec = {'go_id': go_id,
                       'agreementnumber': go_id,
                       # 'transtypeid': '1',
                       'transactiondate': datetime.today(),
                       'transactionsourceid': 'GO8',
                       'transtypedesc': 'Charges Payment',
                       'transflag': 'Col',
                       'transfallendue': '0',
                       'transnetpayment': -round(Decimal(collected3)/Decimal(config.other_sales_tax),2),
                       'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                       'transpayprointerest': -round(Decimal(collected3)/Decimal(config.other_sales_tax),2),
                       }
        go_account_transaction_detail(**charges_rec).save()
    if Decimal(collected4) > 0:
        risk_fee_rec = {'go_id': go_id,
                       'agreementnumber': go_id,
                       'transtypeid': '3',
                       'transactiondate': datetime.today(),
                       'transactionsourceid': 'GO8',
                       'transtypedesc': 'Risk Fee Payment',
                       'transflag': 'Col',
                       'transfallendue': '0',
                       'transnetpayment': -round(Decimal(collected4)/Decimal(config.other_sales_tax),2),
                       'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                       'transpayprointerest': -round(Decimal(collected4)/Decimal(config.other_sales_tax),2),
                       }
        go_account_transaction_detail(**risk_fee_rec).save()

    if Decimal(collected5) > 0:
        bamf_rec = {'go_id': go_id,
                       'agreementnumber': go_id,
                       'transtypeid': '5',
                       'transactiondate': datetime.today(),
                       'transactionsourceid': 'GO8',
                       'transtypedesc': 'BAMF Payment',
                       'transflag': 'Col',
                       'transfallendue': '0',
                       'transnetpayment': -round(Decimal(collected5)/Decimal(config.other_sales_tax),2),
                       'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                       'transpayprointerest': -round(Decimal(collected5)/Decimal(config.other_sales_tax),2),
                       }
        go_account_transaction_detail(**bamf_rec).save()

    if Decimal(collected6) > 0:
        secondaries_rec = {'go_id': go_id,
                       'agreementnumber': go_id,
                       'transtypeid': '1',
                       'transactiondate': datetime.today(),
                       'transactionsourceid': 'GO8',
                       'transtypedesc': 'Secondaries Payment',
                       'transflag': 'Col',
                       'transfallendue': '0',
                       'transnetpayment': -round(Decimal(collected6)/Decimal(config.other_sales_tax),2),
                       'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                       'transpayprointerest': -round(Decimal(collected6)/Decimal(config.other_sales_tax),2),
                       }
        go_account_transaction_detail(**secondaries_rec).save()

    ats_settlement_rec = {'go_id': go_id,
                          'agreementnumber': go_id,
                          'transtypeid': '14',
                          'transactiondate': datetime.today(),
                          'transactionsourceid': 'GO8',
                          'transtypedesc': 'Settlement Payment',
                          'transflag': 'Col',
                          'transfallendue': '0',
                          'transnetpayment': -round(Decimal(arrears_total_collected)/Decimal(config.other_sales_tax), 2),
                          'transgrosspayment': -Decimal(arrears_total_collected),
                          'transactionsourcedesc' : 'HISTORY',
                          'transagreementagreementdate' : datetime.today(),
                          'transagreementauthority' : agreement_detail.agreementauthority,
                          'transagreementclosedflag_id' : '902',
                          'transactionstatus': '902',
                          'transagreementcustomernumber' : agreement_detail.agreementcustomernumber,
                          'transcustomercompany': agreement_detail.customercompany,
                          'transagreementddstatus_id' : 'I',
                          'transagreementdefname' : 'Agreement Finished',
                          'transddpayment' : '0' ,
                          'transnetpaymentcapital': -Decimal(collected2)/Decimal(config.other_sales_tax),
                          'transnetpaymentinterest': -Decimal(collected3)/Decimal(config.other_sales_tax),
                          }

    write_off_value_net = Decimal(wip_element_value) - (Decimal(arrears_total_collected)) / Decimal(config.other_sales_tax)
    if write_off_value > 0:
        write_off_rec = {'go_id': go_id,
                         'agreementnumber': go_id,
                         'transtypeid': '5',
                         'transactiondate': datetime.today(),
                         'transactionsourceid': 'GO8',
                         'transtypedesc': 'Write-off Payment',
                         'transflag': 'Col',
                         'transfallendue': '0',
                         'transnetpayment': -round(write_off_value_net,2),
                         'transgrosspayment': -write_off_value,
                         'transactionsourcedesc': 'HISTORY',
                         'transagreementagreementdate': datetime.today(),
                         'transagreementauthority': agreement_detail.agreementauthority,
                         'transagreementclosedflag_id': '902',
                         'transactionstatus': '902',
                         'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                         'transcustomercompany': agreement_detail.customercompany,
                         'transagreementddstatus_id': 'I',
                         'transagreementdefname': 'Agreement Finished',
                         'transddpayment': '0',
                         'transnetpaymentcapital': -Decimal(adjustment2)/Decimal(config.other_sales_tax),
                         'transnetpaymentinterest': -Decimal(adjustment3)/Decimal(config.other_sales_tax),
                         }

        go_account_transaction_summary(**write_off_rec).save()

    if Decimal(adjustment1) > 0:
        doc_fee_rec = {'go_id': go_id,
                       'agreementnumber': go_id,
                       'transtypeid': '1',
                       'transactiondate': datetime.today(),
                       'transactionsourceid': 'GO8',
                       'transtypedesc': arrears_total_adjustment1,
                       'transflag': 'Col',
                       'transfallendue': '0',
                       'transnetpayment': -round(Decimal(adjustment1) / Decimal(config.other_sales_tax),2),
                       }
        go_account_transaction_detail(**doc_fee_rec).save()
        doc_fee_rec
    if Decimal(adjustment2) > 0:
        principal_rec = {'go_id': go_id,
                         'agreementnumber': go_id,
                         # 'transtypeid': '1',
                         'transactiondate': datetime.today(),
                         'transactionsourceid': 'GO8',
                         'transtypedesc': arrears_total_adjustment2,
                         'transflag': 'Col',
                         'transfallendue': '0',
                         'transnetpayment': -round(Decimal(adjustment2) / Decimal(config.other_sales_tax),2)
                         }
        go_account_transaction_detail(**principal_rec).save()

    if Decimal(adjustment3) > 0:
        charges_rec = {'go_id': go_id,
                       'agreementnumber': go_id,
                       # 'transtypeid': '1',
                       'transactiondate': datetime.today(),
                       'transactionsourceid': 'GO8',
                       'transtypedesc': arrears_total_adjustment3,
                       'transflag': 'Col',
                       'transfallendue': '0',
                       'transnetpayment': -round(Decimal(adjustment3) / Decimal(config.other_sales_tax),2),
                       }
        go_account_transaction_detail(**charges_rec).save()
    if Decimal(adjustment4) > 0:
        risk_fee_rec = {'go_id': go_id,
                        'agreementnumber': go_id,
                        'transtypeid': '3',
                        'transactiondate': datetime.today(),
                        'transactionsourceid': 'GO8',
                        'transtypedesc': arrears_total_adjustment4,
                        'transflag': 'Col',
                        'transfallendue': '0',
                        'transnetpayment': -round(Decimal(adjustment4) / Decimal(config.other_sales_tax),2),
                        }
        go_account_transaction_detail(**risk_fee_rec).save()

    if Decimal(adjustment5) > 0:
        bamf_rec = {'go_id': go_id,
                    'agreementnumber': go_id,
                    'transtypeid': '5',
                    'transactiondate': datetime.today(),
                    'transactionsourceid': 'GO8',
                    'transtypedesc': arrears_total_adjustment5,
                    'transflag': 'Col',
                    'transfallendue': '0',
                    'transnetpayment': -round(Decimal(adjustment5) / Decimal(config.other_sales_tax),2),
                    }
        go_account_transaction_detail(**bamf_rec).save()

    if Decimal(adjustment6) > 0:
        secondaries_rec = {'go_id': go_id,
                           'agreementnumber': go_id,
                           # 'transtypeid': '1',
                           'transactiondate': datetime.today(),
                           'transactionsourceid': 'GO8',
                           'transtypedesc': arrears_total_adjustment6,
                           'transflag': 'Col',
                           'transfallendue': '0',
                           'transnetpayment': -round(Decimal(adjustment6) / Decimal(config.other_sales_tax),2),
                           }
        go_account_transaction_detail(**secondaries_rec).save()

    other_rounding_value = round((Decimal(write_off_value) + Decimal(arrears_total_collected))/ Decimal(config.other_sales_tax),2)-wip_element_value

    if write_off_value <= 0:
        round_off_rec = {'go_id': go_id,
                         'agreementnumber': go_id,
                         'transtypeid': '5',
                         'transactiondate': datetime.today(),
                         'transactionsourceid': 'GO8',
                         'transtypedesc': 'Rounding Correction',
                         'transflag': 'Col',
                         'transfallendue': '0',
                         'transnetpayment': other_rounding_value,
                         'transgrosspayment': 0,
                         'transactionsourcedesc': 'HISTORY',
                         'transagreementagreementdate': datetime.today(),
                         'transagreementauthority': agreement_detail.agreementauthority,
                         'transagreementclosedflag_id': '902',
                         'transactionstatus': '902',
                         'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                         'transcustomercompany': agreement_detail.customercompany,
                         'transagreementddstatus_id': 'I',
                         'transagreementdefname': 'Agreement Finished',
                         'transddpayment': '0',
                         'transnetpaymentcapital': Decimal(re.sub(',', '', '0.00')),
                         'transnetpaymentinterest': Decimal(re.sub(',', '', '0.00')),
                         }
        go_account_transaction_summary(**round_off_rec).save()
    round_off_ats = {'go_id': go_id,
                     'agreementnumber': go_id,
                     'transtypeid': '5',
                     'transactiondate': datetime.today(),
                     'transactionsourceid': 'GO8',
                     'transtypedesc': 'Rounding Correction',
                     'transflag': 'Col',
                     'transfallendue': '0',
                     'transnetpayment': other_rounding_value,
                     'transpayproprincipal': Decimal(re.sub(',', '', '0.00')),
                     'transpayprointerest': other_rounding_value,
                     }
    go_account_transaction_detail(**round_off_ats).save()



    go_agreement_querydetail.objects.filter(agreementnumber=agreement_id
                                      ).update(agreement_closed_reason= 'Settled')
    go_account_transaction_summary.objects.filter(go_id=go_id).update(transagreementclosedflag_id='902')
    go_account_transaction_summary.objects.filter(go_id=go_id, transactiondate__gt=datetime.today()).update(transactionstatus='902')

    go_agreements.objects.filter(go_id=go_id
                                      ).update(agreementstatus='CLOSED',
                                               agreementautostatus='CLOSED(Settled)',
                                               agreementclosedflag_id='902')
    go_agreement_querydetail.objects.filter(go_id=go_id
                                 ).update(agreementstatus='CLOSED',
                                          agreementautostatus='CLOSED(Settled)',
                                          agreementclosedflag_id='902',
                                          closeddate=datetime.now())

    go_id.agreement_origin_flag = 'GO'

    go_account_transaction_summary(**ats_settlement_rec).save()
    go_id.settled_date = datetime.now()
    go_id.save()


def settlement_documentation_function(request,agreement_id):
    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)

    go_settlement.objects.filter(go_id=go_id).update(sent_to_customer='Archived')

    arrears_total_arrears = request.POST.get('arrears_total_arrears')
    arrears_total_collected = request.POST.get('arrears_total_collected')
    arrears_total_adjustment = request.POST.get('arrears_total_adjustment')

    arrears_total_adjustment1 = request.POST.get('arrears_total_adjustment1')
    arrears_total_adjustment2 = request.POST.get('arrears_total_adjustment2')
    arrears_total_adjustment3 = request.POST.get('arrears_total_adjustment3')
    arrears_total_adjustment4 = request.POST.get('arrears_total_adjustment4')
    arrears_total_adjustment5 = request.POST.get('arrears_total_adjustment5')
    arrears_total_adjustment6 = request.POST.get('arrears_total_adjustment6')

    collected1 = request.POST.get('collected1')
    collected2 = request.POST.get('collected2')
    collected3 = request.POST.get('collected3')
    collected4 = request.POST.get('collected4')
    collected5 = request.POST.get('collected5')
    collected6 = request.POST.get('collected6')

    adjustment1 = request.POST.get('adjustment1')
    adjustment2 = request.POST.get('adjustment2')
    adjustment3 = request.POST.get('adjustment3')
    adjustment4 = request.POST.get('adjustment4')
    adjustment5 = request.POST.get('adjustment5')
    adjustment6 = request.POST.get('adjustment6')

    balance1 = request.POST.get('balance1')
    balance2 = request.POST.get('balance2')
    balance3 = request.POST.get('balance3')
    balance4 = request.POST.get('balance4')
    balance5 = request.POST.get('balance5')
    balance6 = request.POST.get('balance6')



    totals_ats = {'go_id': go_id,
                  'agreement_id': go_id,
                  'calculated': arrears_total_arrears,
                  'actuals': arrears_total_collected,
                  'adjustment': arrears_total_adjustment,
                  'description': 'Total Values',
                  'sent_to_customer': 'Live',
                  }

    line1_ats = {'go_id': go_id,
                  'agreement_id': go_id,
                  'calculated': balance1,
                  'actuals': collected1,
                  'adjustment': adjustment1,
                  'description': 'Doc Fee Values',
                  'reason': arrears_total_adjustment1,
                  'sent_to_customer': 'Live',
                  }
    line2_ats = {'go_id': go_id,
                 'agreement_id': go_id,
                 'calculated': balance2,
                 'actuals': collected2,
                 'adjustment': adjustment2,
                 'description': 'Principal Values',
                 'reason': arrears_total_adjustment2,
                 'sent_to_customer': 'Live',
                 }

    line3_ats = {'go_id': go_id,
                 'agreement_id': go_id,
                 'calculated': balance3,
                 'actuals': collected3,
                 'adjustment': adjustment3,
                 'description': 'Charges Values',
                 'reason': arrears_total_adjustment3,
                 'sent_to_customer': 'Live',
                 }

    line4_ats = {'go_id': go_id,
                 'agreement_id': go_id,
                 'calculated': balance4,
                 'actuals': collected4,
                 'adjustment': adjustment4,
                 'description': 'Charges Values',
                 'reason': arrears_total_adjustment4,
                 'sent_to_customer': 'Live',
                 }

    line5_ats = {'go_id': go_id,
                 'agreement_id': go_id,
                 'calculated': balance5,
                 'actuals': collected5,
                 'adjustment': adjustment5,
                 'description': 'Charges Values',
                 'reason': arrears_total_adjustment5,
                 'sent_to_customer': 'Live',
                 }

    line6_ats = {'go_id': go_id,
                 'agreement_id': go_id,
                 'calculated': balance6,
                 'actuals': collected6,
                 'adjustment': adjustment6,
                 'description': 'Charges Values',
                 'reason': arrears_total_adjustment6,
                 'sent_to_customer': 'Live',
                 }

    go_settlement(**totals_ats).save()
    go_settlement(**line1_ats).save()
    go_settlement(**line2_ats).save()
    go_settlement(**line3_ats).save()
    go_settlement(**line4_ats).save()
    go_settlement(**line5_ats).save()
    go_settlement(**line6_ats).save()


def reopen_function(request, agreement_id):

    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    instalmentnet = str(agreement_detail.agreementinstalmentnet)
    agreement_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    customer = agreement_detail.customercompany

    history_change_date = {'go_id': go_id,
                           'agreement_id': agreement_id,
                           'user': request.user,
                           'updated': datetime.now(),
                           'action': 'Reopened',
                           # 'transaction': format(transaction_date,'%d/%m/%Y'),

                           'customercompany': customer
                               }
    go_editor_history(**history_change_date).save()

    go_account_transaction_summary.objects.filter(go_id=go_id, transactionsourceid= 'GO8').delete()
    go_account_transaction_detail.objects.filter(go_id=go_id, transactionsourceid= 'GO8').delete()

    go_account_transaction_summary.objects.filter(go_id=go_id).update(transagreementclosedflag_id='901')
    go_account_transaction_summary.objects.filter(go_id=go_id, transactiondate__gt=datetime.today()).update(transactionstatus='901')

    go_agreement_querydetail.objects.filter(agreementnumber=agreement_id
                                      ).update(agreement_closed_reason='')

    go_agreements.objects.filter(go_id=go_id
                                      ).update(agreementstatus='REOPENED',
                                               agreementautostatus='REOPENED',
                                               agreementclosedflag_id='901')
    go_agreement_querydetail.objects.filter(go_id=go_id
                                 ).update(agreementstatus='REOPENED',
                                          agreementautostatus='REOPENED',
                                          agreementclosedflag_id='901')

    if not go_id.manual_payments:
        try:
            dd_history = DDHistory.objects.get(agreement_no=agreement_id, sequence='9999')
            args = (
                agreement_id,
                generate_dd_reference(agreement_id),
                dd_history.account_name,
                dd_history.account_number,
                dd_history.sort_code
            )
            create_ddi_with_datacash(*args, user=request.user)
        except Exception as e:
            pass

def archive_agreement_function(request, agreement_id):
    print('test')

    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)

    go_agreement_querydetail.objects.filter(agreementnumber=agreement_id
                                            ).update(agreement_closed_reason='Archived')
    go_account_transaction_summary.objects.filter(go_id=go_id).update(transagreementclosedflag_id='902')
    go_account_transaction_summary.objects.filter(go_id=go_id, transactiondate__gt=datetime.today()).update(
        transactionstatus='902')

    go_agreements.objects.filter(go_id=go_id
                                 ).update(agreementstatus='CLOSED',
                                          agreementautostatus='CLOSED(Archived)',
                                          agreementclosedflag_id='902')
    go_agreement_querydetail.objects.filter(go_id=go_id
                                            ).update(agreementstatus='CLOSED',
                                                     agreementautostatus='CLOSED(Archived)',
                                                     agreementclosedflag_id='902',
                                                     closeddate=datetime.now())

def unarchive_agreement_function(request, agreement_id):
    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)

    go_agreement_querydetail.objects.filter(agreementnumber=agreement_id
                                            ).update(agreement_closed_reason='')
    go_account_transaction_summary.objects.filter(go_id=go_id).update(transagreementclosedflag_id='901')
    go_account_transaction_summary.objects.filter(go_id=go_id, transactiondate__gt=datetime.today()).update(
        transactionstatus='901')

    go_agreements.objects.filter(go_id=go_id
                                 ).update(agreementstatus='REOPENED',
                                          agreementautostatus='REOPENED',
                                          agreementclosedflag_id='901')
    go_agreement_querydetail.objects.filter(go_id=go_id
                                            ).update(agreementstatus='REOPENED',
                                                     agreementautostatus='REOPENED',
                                                     agreementclosedflag_id='901',
                                                     closeddate=datetime.now())

    query_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)

    try:
        args = (
            agreement_id,
            generate_dd_reference(agreement_id),
            query_detail.agreementbankaccountname,
            query_detail.agreementbankaccountnumber,
            query_detail.agreementbanksortcode
        )
        create_ddi_with_datacash(*args, user=request.user)
    except:
        pass


def refund_function(request, agreement_id):

    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    agreement_detail = go_agreement_querydetail.objects.get(go_id=go_id)
    config = client_configuration.objects.get(client_id='NWCF')

    date = datetime.strptime(request.POST['refund_date'], "%Y-%m-%d")
    if request.POST['refund_amount']:
        amount = Decimal(re.sub(',', '', request.POST['refund_amount']))
    else:
        return

    net_amount = amount
    gross_amount = amount

    if agreement_detail.agreementdefname == 'Lease Agreement':
        net_amount = round(amount / Decimal(config.other_sales_tax), 2)

    ats_refund_rec = {'go_id': go_id,
                      'agreementnumber': go_id,
                      'transtypeid': '3',
                      'transactiondate': date,
                      'transactionsourceid': 'GO7',
                      'transtypedesc': 'Refund',
                      'transflag': 'Col',
                      'transfallendue': '0',
                      'transnetpayment': net_amount,
                      'transpayproprincipal': Decimal(0),
                      'transpayprointerest': net_amount,
    }
    go_account_transaction_detail(**ats_refund_rec).save()

    atd_refund_rec = {'go_id': go_id,
                      'agreementnumber': go_id,
                      'transtypeid': '3',
                      'transactiondate': date,
                      'transactionsourceid': 'GO7',
                      'transtypedesc': 'Refund',
                      'transflag': 'Col',
                      'transfallendue': '0',
                      'transnetpayment': net_amount,
                      'transgrosspayment': gross_amount,
                      'transactionsourcedesc': 'Refund',
                      'transagreementagreementdate': datetime.today(),
                      'transagreementauthority': agreement_detail.agreementauthority,
                      'transagreementclosedflag_id': '901',
                      'transactionstatus': '901',
                      'transagreementcustomernumber': agreement_detail.agreementcustomernumber,
                      'transcustomercompany': agreement_detail.customercompany,
                      'transagreementddstatus_id': 'I',
                      'transagreementdefname': '',
                      'transddpayment': '0',
                      'transnetpaymentcapital': Decimal(0),
                      'transnetpaymentinterest': net_amount,
    }

    go_agreement_index.objects.filter(go_id=go_id).update(agreement_origin_flag='GO')

    go_account_transaction_summary(**atd_refund_rec).save()

