import datetime
from django.db.models import Q
import requests

from core_agreement_crud.models import go_agreement_index, go_agreement_querydetail, go_account_transaction_summary,\
                                       go_account_transaction_detail, go_customers, go_broker, go_agreements, transition_log, go_funder
from core_agreement_editor.models import go_editor_history

from core_dd_drawdowns.models import DDHistory
from core_direct_debits.functions import create_ddi_with_datacash, generate_dd_reference, cancel_ddi_with_datacash

try:
    BROKER = go_broker.objects.get(broker_description='Broker')
    NON_BROKER = go_broker.objects.get(broker_description='Non-Broker')
    BLUEROCK = go_funder.objects.get(funder_code=2)
except:
    BROKER = None
    NON_BROKER = None
    BLUEROCK = None

def convert_to_go_agreement(agreement_id, user):

    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    agreement = go_agreements.objects.get(agreementnumber=agreement_id)
    query_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    customer = go_customers.objects.get(customernumber=query_detail.agreementcustomernumber)

    # Update go_agreement_index object.
    # ---------------------------------

    if go_id.agreement_origin_flag in ('TR', 'GO'):
        return True

    go_id.term = agreement.agreementnumpayments
    go_id.amf_flag = 1
    go_id.risk_flag = 0
    go_id.bamf_flag = 1
    go_id.security_flag = 1
    go_id.secondary_flag = 1
    go_id.broker = NON_BROKER
    go_id.funder = BLUEROCK
    if len(agreement_id) == 5 and int(agreement_id[:1]) == 9:
        # TODO: Other company configurations
        go_id.broker = BROKER
    go_id.agreement_doc_fee = 0.00
    go_id.title_flag = 1
    go_id.agreement_instalment_gross = agreement.agreementinstalmentnet
    if agreement.agreementinstalmentvat:
        go_id.agreement_instalment_gross += agreement.agreementinstalmentvat
    go_id.agreement_total_fees = agreement.agreementtotalfees
    go_id.agreement_payable_net = 0.00
    go_id.agreement_payable_gross = 0.00
    go_id.agreement_risk_fee = 0.00
    go_id.agreement_bamf_fee = 0.00
    go_id.funder = go_funder.objects.get(funder_code=2)
    go_id.save()
    print(go_id)
    print('test 1558')

    if query_detail.agreementpaymentmethod != 12:
        go_id.manual_payments = 1

    query_detail.agreement_stage = '4'
    query_detail.save()

    # Is risk fee applied?
    # --------------------
    if go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                    transtypedesc='Risk Fee').exists():
        go_id.risk_flag = 1

    # Is bamf applied?
    # --------------------
    if go_account_transaction_detail.objects.filter(Q(transtypedesc='Bi-Annual Management Fee') | Q(transtypedesc='Bi-Annual Anniversary Fee'),
                                                    agreementnumber=agreement_id).exists():
        go_id.bamf = 1

    # Is doc fee applied?
    # -------------------
    try:
        doc_fees = go_account_transaction_detail.objects.filter(agreementnumber=agreement_id,
                                                                transtypedesc='Documentation Fee').order_by('-id')
        if doc_fees:
            go_id.agreement_doc_fee = doc_fees[0].transnetpayment
        else:
            go_id.agreement_doc_fee = 0
    except:
        go_id.agreement_doc_fee = 0

    go_id.save()

    # Account manager lookup
    # SKIPPED SKIPPED SKIPPED !!!!!



    # Update email
    # ------------
    customer.customeremail = 'sentinel@gofintech.co.uk'
    customer.save()

    # Get originating datacash reference
    # ----------------------------------

    ref = agreement.agreementbankreference
    dd_ref = agreement.agreementdatacashmerchantref

    if dd_ref:
        if len(dd_ref) == 16:
            dd_ref = dd_ref[6:]

    if ref and dd_ref:
        DDHistory.objects.filter(reference=ref).update(dd_reference=dd_ref)
        agreement.agreementdatacashmerchantref = dd_ref
        agreement.save()
        # cancel_ddi_with_datacash(agreement_id))
        # TODO: Decide if we should cancel old dd from sentinel
    else:
        try:
            args = (
                agreement_id,
                'GO{}'.format(generate_dd_reference(agreement_id)),
                query_detail.agreementbankaccountname,
                query_detail.agreementbankaccountnumber,
                query_detail.agreementbanksortcode
            )
            create_ddi_with_datacash(*args, user=user)


        except:
            pass

    # SP1 -> GO1
    go_account_transaction_detail.objects.filter(transactionsourceid='SP1',
                                                 agreementnumber=agreement_id).update(transactionsourceid='GO1')
    go_account_transaction_summary.objects.filter(transactionsourceid='SP1',
                                                  agreementnumber=agreement_id).update(transactionsourceid='GO1', transactionstatus='901')

    # SP2 -> GO3
    go_account_transaction_summary.objects.filter(transactionsourceid='SP2',
                                                  agreementnumber=agreement_id).update(transactionsourceid='GO3', transactionstatus='901')
    go_account_transaction_detail.objects.filter(transactionsourceid='SP2',
                                                 agreementnumber=agreement_id).update(transactionsourceid='GO3')

    # SP3 -> GO3
    go_account_transaction_summary.objects.filter(transactionsourceid='SP3',
                                                  agreementnumber=agreement_id).update(transactionsourceid='GO3', transactionstatus='901')
    go_account_transaction_detail.objects.filter(transactionsourceid='SP3',
                                                 agreementnumber=agreement_id).update(transactionsourceid='GO3')

    # SP9 -> GO9
    go_account_transaction_summary.objects.filter(transactionsourceid='SP9',
                                                  agreementnumber=agreement_id).update(transactionsourceid='GO9', transactionstatus='901')
    go_account_transaction_detail.objects.filter(transactionsourceid='SP9',
                                                 agreementnumber=agreement_id).update(transactionsourceid='GO9')
    # go_account_transaction_summary.objects.filter(agreementnumber=agreement_id).update(transagreementclosedflag='901')
    go_id.agreement_origin_flag = 'TR'
    go_id.save()

    transition = {'agreementnumber' : agreement_id,
                     'from_system' : 'Sentinel',
                     'to_system' : 'GO',
                  }

    transition_log(**transition).save()

    history_change_dates = {'go_id': go_id,
                            'agreement_id': agreement_id,
                            'user': user,
                            # 'updated': datetime.now(),
                            'action': 'Converted from Sentinel to GO',
                            'transaction': 'All Transactions',
                            'customercompany': customer.customercompany,
                            }
    go_editor_history(**history_change_dates).save()

    return True


def convert_back_to_sentinal(agreement_id, user):

    go_id = go_agreement_index.objects.get(agreement_id=agreement_id)
    query_detail = go_agreement_querydetail.objects.get(agreementnumber=agreement_id)
    customer = go_customers.objects.get(customernumber=query_detail.agreementcustomernumber)

    if not go_id.agreement_origin_flag or go_id.agreement_origin_flag == 'GO':
        return True

    try:
        cancel_ddi_with_datacash(agreement_id)
    except Exception as e:
        print(e)
        pass

    go_id.agreement_origin_flag = None
    go_id.save()

    transition = {'agreementnumber': agreement_id,
                  'from_system': 'GO',
                  'to_system': 'Sentinel',
                  }

    transition_log(**transition).save()

    history_change_dates = {'go_id': go_id,
                            'agreement_id': agreement_id,
                            'user': user,
                            # 'updated': datetime.now(),
                            'action': 'Converted from GO to Sentinel',
                            'transaction': 'All Transactions',
                            'customercompany': customer.customercompany,
                            }
    go_editor_history(**history_change_dates).save()

    return True
