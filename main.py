import json
import firebase_admin
from datetime import datetime
from firebase_admin import credentials
from firebase_admin import firestore
from passlib.hash import pbkdf2_sha256
from flask import Flask, render_template, request, session, flash, url_for, redirect, make_response

# authorizenet
from authorizenet import apicontractsv1
from authorizenet.apicontrollers import createTransactionController
from authorizenet.apicontrollers import *
from decimal import *

# algolia search api
from algoliasearch import algoliasearch

# twilio for sending msg alert
from twilio.rest import Client

# Use a service account
cred = credentials.Certificate('config.json')
firebase_admin.initialize_app(cred)

# database connection
db = firestore.client()

# flask connection
app = Flask(__name__)
app.cfg = json.load(open('config.json', 'r'))
app.secret_key = json.load(open('config.json', 'r')).get('project_id', 'qwerty')
app.config['SESSION_TYPE'] = 'filesystem'

# algolia app connection
client = algoliasearch.Client(app.cfg.get('app_id'), app.cfg.get('admin_api_key'))
index = client.init_index('posts')


@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    thought_data, event_data, algo_tot = [], [], []
    # Post and stuff
    try:
        thought_data = []
        thought_ref = db.collection('thoughts')
        for th_doc in thought_ref.get():
            thought_data.append(th_doc.to_dict())
    except Exception as e:
        thought_data = []
        print(e)

    # Post and stuff
    try:
        event_data = []
        event_ref = db.collection('events')
        for ev_doc in event_ref.get():
            ev_doc.to_dict()['event_date'] = datetime.strptime(ev_doc.to_dict().get('event_date'),
                                                               "%Y-%m-%d").strftime("%B %d, %Y")
            event_data.append(ev_doc.to_dict())
    except Exception as e:
        event_data = []
        print(e)

    return render_template('index.html', thought_data=reversed(thought_data), event_data=reversed(event_data))


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    user_detail = {}
    msg = ""
    ev=dict()
    job_data, thought_data, event_data, results = [], [], [], []

    show_info = {}
    if 'logged_in' in session:

        if 'msg' in dict(request.args):
            msg = dict(request.args)['msg']

        # User details
        try:
            user_ref = db.collection('users').document(session['username']).get()
            user_detail['full_name'] = user_ref.get('full_name')
            user_detail['state'] = user_ref.get('state')
            user_detail['dob'] = datetime.strptime(user_ref.get('dob'), "%m-%d-%Y").strftime("%B %d, %Y")
            user_detail['skill'] = user_ref.get('skill')
        except Exception as e:
            print(e)

        if 'tm_type' in dict(request.args):
            tm_type = dict(request.args)['tm_type'][0]
            show_info['tm_type'] = tm_type

            if tm_type == 'resources':
                # jobs and stuff
                try:
                    job_data = []
                    job_ref = db.collection('jobs')
                    for job_doc in job_ref.get():
                        job_data.append(job_doc.to_dict())
                except Exception as e:
                    job_data = []
                    print(e)

            if tm_type == 'events':
                # Post and stuff
                try:
                    event_data = []
                    event_ref = db.collection('events')
                    for ev_doc in event_ref.get():
                        ev_doc.to_dict()['event_date'] = datetime.strptime(ev_doc.to_dict().get('event_date'),
                                                                           "%Y-%m-%d").strftime("%B %d, %Y")
                        event_data.append(ev_doc.to_dict())
                except Exception as e:
                    event_data = []
                    print(e)

        # Post and stuff
        try:
            event_ref = db.collection('events')
            for ev_doc in event_ref.get():
                ev_doc.to_dict()['event_date'] = datetime.strptime(ev_doc.to_dict().get('event_date'),
                                                                   "%Y-%m-%d").strftime("%B %d, %Y")
                ev = ev_doc.to_dict()
        except Exception as e:
            print(e)

        if 'tm_type' not in dict(request.args) or tm_type == 'posts':
            # Post and stuff
            try:
                thought_data = []
                thought_ref = db.collection('thoughts')
                for th_doc in thought_ref.get():
                    thought_data.append(th_doc.to_dict())
            except Exception as e:
                thought_data = []
                print(e)

        if 'result' in dict(request.args):
            results = dict(request.args)['result']
            if results:
                results = json.loads(results[0])

        return render_template('dashboard.html', user_detail=user_detail, msg=msg, job_data=reversed(job_data),
                               thought_data=reversed(thought_data), event_data=reversed(event_data),
                               show_info=show_info, results=results, ev=ev)
    err = 'Login Required'
    return render_template('index.html', err=err)


@app.route('/post_thought', methods=['GET', 'POST'])
def post_thought():
    if request.method == 'POST':
        filename = ''
        thoughts = db.collection('thoughts')
        try:
            for thought in thoughts.get():
                thought_id = int(thought.id)
            thought_id += 1
        except:
            thought_id = 0
        user_ref = db.collection('users').document(session['username']).get()
        full_name = user_ref.get('full_name')
        img_file = request.files.get('fileToUpload')
        if img_file:
            img_file.save('static/img/' + img_file.filename)
            filename = img_file.filename

        post_thought = {
            'mem_uploaded': full_name,
            'thought': request.form.get('thought'),
            'image_name': 'img/{}'.format(str(filename)),
            'date': datetime.today().strftime("%B %d, %Y")
        }
        thoughts = db.collection('thoughts').document(str(thought_id))
        thoughts.set(post_thought)
        index.add_object(post_thought)
        msg = 'Posted'
        return redirect(url_for('dashboard', msg=msg, tm_type='posts'))
    msg = 'Unable to post'
    return redirect(url_for('dashboard', msg=msg))


@app.route('/jobPosting', methods=['GET', 'POST'])
def job_posting():
    if request.method == 'POST':
        jobs = db.collection('jobs')
        try:
            for job in jobs.get():
                job_id = int(job.id)
            job_id += 1
        except:
            job_id = 0

        user_ref = db.collection('users').document(session['username']).get()
        full_name = user_ref.get('full_name')

        job_details = {
            'mem_uploaded': full_name,
            'title': request.form.get('job_title'),
            'description': request.form.get('job_desc'),
            'url': request.form.get('job_url'),
            'date': datetime.today().strftime("%B %d, %Y")
        }
        jobs = db.collection('jobs').document(str(job_id))
        jobs.set(job_details)
        msg = 'Job Posted'
        return render_template('dashboard.html', msg=msg, tm_type='resources')
    msg = 'Unable to post the job'
    return render_template('dashboard.html', msg=msg)


@app.route('/addEvent', methods=['GET', 'POST'])
def add_event():
    if request.method == 'POST':
        events = db.collection('events')
        try:
            for event in events.get():
                event_id = int(event.id)
            event_id += 1
        except:
            event_id = 0

        user_ref = db.collection('users').document(session['username']).get()
        full_name = user_ref.get('full_name')

        event_details = {
            'mem_uploaded': full_name,
            'event_name': request.form.get('event_name'),
            'event_details': request.form.get('event_details'),
            'event_date': request.form.get('event_date')
        }
        events = db.collection('events').document(str(event_id))
        events.set(event_details)
        index.add_object(event_details)
        user_all = db.collection('users')
        for usr in user_all.get():
            msg = ''
            full_name = usr.to_dict().get('full_name')
            contact = usr.to_dict().get('phone')
            msg += '\nHi {}\n New Event has been Posted! Check it out\nEvent Name {}\n Event Date:{}!!\n Event ' \
                   'Description: {}\n '.format(full_name, request.form.get('event_name'),
                                               request.form.get('event_date'),
                                               request.form.get('event_details'))
            if send_alert(msg, contact):
                print(True)
            else:
                print(False)
        msg = 'Added Event successfully'
        return redirect(url_for('dashboard', msg=msg, tm_type='events'))
    return redirect(url_for('dashboard'))


@app.route('/add_skill', methods=['GET', 'POST'])
def add_skill():
    if request.method == "POST":
        user_r = db.collection('users').document(session['username'])
        try:
            skill = user_r.get().get('skill')
            skill.append(request.form.get('skill'))
        except:
            skill = [request.form.get('skill')]
        user_r.set({'skill': skill}, merge=True)
        msg = 'Added successfully'
        return redirect(url_for('dashboard', msg=msg))
    return redirect(url_for('dashboard'))


@app.route('/userLogin', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        try:
            user_ref = db.collection('users').document(request.form.get('email'))
            user = user_ref.get()
        except Exception:
            err = 'User not found'
            return render_template('login.html', err=err)
        if request.form.get('password'):
            if not pbkdf2_sha256.verify(request.form.get('password'), user.get('password')):
                err = 'Password or Username is incorrect.'
                return render_template('login.html', err=err)
            else:
                session['username'] = user.get('email')
                session['acc_type'] = user.get('acc_type')
                session['logged_in'] = True
                msg = 'You have been successfully logged'
                return redirect(url_for('dashboard', msg=msg))
        return render_template('login.html', err="Unable to login")
    return render_template('login.html')


@app.route('/userSignup', methods=['GET', 'POST'])
def user_signup():
    if request.method == 'POST':
        try:
            phone = str(request.form.get("phone")) if len(request.form.get("phone")) == 10 else None
            if phone is None:
                return render_template('signup.html', err=" Please check the phone number")
            user_details = {
                'full_name': request.form.get('full_name'),
                'email': request.form.get('email'),
                'password': pbkdf2_sha256.hash(str(request.form.get('password'))),
                'dob': '{}-{}-{}'.format(request.form.get("dob_mm"),
                                         request.form.get("dob_dd"),
                                         request.form.get("dob_yy")),
                'gender': request.form.get("gender"),
                'street': request.form.get("street"),
                'city': request.form.get("city"),
                'state': request.form.get("state"),
                'zip': request.form.get("zip"),
                'phone': phone,
                'acc_type': request.form.get('acc_type'),
                'about': request.form.get('Highlight')
                # 'pay_mode': request.form.get('payment-method'),
                # 'card_number': pbkdf2_sha256.hash(str(request.form.get('card-number'))),
                # 'pin': pbkdf2_sha256.hash(str('pin'))
            }
            user = db.collection('users').document(str(request.form.get('email')))
            user.set(user_details)
        except:
            err = "Unsuccessful! Try again"
            return render_template('signup.html', err=err)

        session['username'] = str(request.form.get('email'))
        session['acc_type'] = str(request.form.get('acc_type'))
        session['logged_in'] = True
        msg = 'You have been successfully logged'
        return redirect(url_for('dashboard', msg=msg))
    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('logged_in', None)
    session.clear()
    msg = 'You have been successfully logged out.'
    return redirect(url_for('home', msg=msg))


@app.errorhandler(404)
def page_not_found(e):
    return render_template('Error404.html')


@app.route('/donate')
def donate():
    return render_template('donate.html', loginID=CONSTANTS.apiLoginId, clientkey=CONSTANTS.transactionKey)


@app.route('/search', methods=['GET', 'POST'])
def algolia_search():
    result = []
    sol = {}
    phrase = str(request.form.get('search'))
    try:
        res = index.search(phrase)
        for i, hits in enumerate(res.get('hits')):
            result.append(hits)
            if i==1:
                break
    except:
        pass
    return redirect(url_for('dashboard', result=json.dumps(result)))


def send_alert(body, contact):
    client = Client(app.cfg.get('account_sid'), app.cfg.get('auth_token'))
    try:
        message = client.messages.create(
            from_=app.cfg.get('from_'),
            body=body,
            to='+1{}'.format(contact)
        )
        return message.sid
    except:
        return False


"""
Charge a credit card
"""

import imp

CONSTANTS = imp.load_source('modulename', 'constants.py')

@app.route('/pay', methods=['POST'])
def charge_credit_card():
    """
    Charge a credit card
    """
    # if 'card-number' in dict(request.args):
            # card_number = dict(request.args)['card-number']

    amount = request.form.get('Amount')
    # Create a merchantAuthenticationType object with authentication details
    # retrieved from the constants file
    merchantAuth = apicontractsv1.merchantAuthenticationType()
    merchantAuth.name = CONSTANTS.apiLoginId
    merchantAuth.transactionKey = CONSTANTS.transactionKey

    # Create the payment data for a credit card
    creditCard = apicontractsv1.creditCardType()
    creditCard.cardNumber = request.form.get('card-number')
    creditCard.expirationDate = "{}-{}".format(request.form.get('card_yy'),request.form.get('card_mm'))
    creditCard.cardCode = request.form.get('pin')

    # Add the payment data to a paymentType object
    payment = apicontractsv1.paymentType()
    payment.creditCard = creditCard

    # Create order information
    order = apicontractsv1.orderType()
    order.invoiceNumber = "10101"
    order.description = "Golf Shirts"

    # Set the customer's Bill To address
    customerAddress = apicontractsv1.customerAddressType()
    customerAddress.firstName = "Ellen"
    customerAddress.lastName = "Johnson"
    customerAddress.company = "Souveniropolis"
    customerAddress.address = "14 Main Street"
    customerAddress.city = "Pecan Springs"
    customerAddress.state = "TX"
    customerAddress.zip = "44628"
    customerAddress.country = "USA"

    # Set the customer's identifying information
    customerData = apicontractsv1.customerDataType()
    customerData.type = "individual"
    customerData.id = "99999456654"
    customerData.email = "EllenJohnson@example.com"

    # Add values for transaction settings
    duplicateWindowSetting = apicontractsv1.settingType()
    duplicateWindowSetting.settingName = "duplicateWindow"
    duplicateWindowSetting.settingValue = "600"
    settings = apicontractsv1.ArrayOfSetting()
    settings.setting.append(duplicateWindowSetting)

    # setup individual line items
    line_item_1 = apicontractsv1.lineItemType()
    line_item_1.itemId = "12345"
    line_item_1.name = "first"
    line_item_1.description = "Here's the first line item"
    line_item_1.quantity = "2"
    line_item_1.unitPrice = "12.95"
    line_item_2 = apicontractsv1.lineItemType()
    line_item_2.itemId = "67890"
    line_item_2.name = "second"
    line_item_2.description = "Here's the second line item"
    line_item_2.quantity = "3"
    line_item_2.unitPrice = "7.95"

    # build the array of line items
    line_items = apicontractsv1.ArrayOfLineItem()
    line_items.lineItem.append(line_item_1)
    line_items.lineItem.append(line_item_2)

    # Create a transactionRequestType object and add the previous objects to it.
    transactionrequest = apicontractsv1.transactionRequestType()
    transactionrequest.transactionType = "authOnlyTransaction"
    transactionrequest.amount = amount
    transactionrequest.payment = payment
    transactionrequest.order = order
    transactionrequest.billTo = customerAddress
    transactionrequest.customer = customerData
    transactionrequest.transactionSettings = settings
    # transactionrequest.lineItems = line_items

    # Assemble the complete transaction request
    createtransactionrequest = apicontractsv1.createTransactionRequest()
    createtransactionrequest.merchantAuthentication = merchantAuth
    createtransactionrequest.refId = "MerchantID-0001"
    createtransactionrequest.transactionRequest = transactionrequest
    # Create the controller
    createtransactioncontroller = createTransactionController(
        createtransactionrequest)
    createtransactioncontroller.execute()

    response = createtransactioncontroller.getresponse()

    if response is not None:
        # Check to see if the API request was successfully received and acted upon
        if response.messages.resultCode == "Ok":
            # Since the API request was successful, look for a transaction response
            # and parse it to display the results of authorizing the card
            if hasattr(response.transactionResponse, 'messages') is True:
                print(
                    'Successfully created transaction with Transaction ID: %s'
                    % response.transactionResponse.transId)
                print('Transaction Response Code: %s' %
                      response.transactionResponse.responseCode)
                print('Message Code: %s' %
                      response.transactionResponse.messages.message[0].code)
                print('Description: %s' % response.transactionResponse.
                      messages.message[0].description)
            else:
                print('Failed Transaction.')
                if hasattr(response.transactionResponse, 'errors') is True:
                    print('Error Code:  %s' % str(response.transactionResponse.
                                                  errors.error[0].errorCode))
                    print(
                        'Error message: %s' %
                        response.transactionResponse.errors.error[0].errorText)
        # Or, print errors if the API request wasn't successful
        else:
            print('Failed Transaction.')
            if hasattr(response, 'transactionResponse') is True and hasattr(
                    response.transactionResponse, 'errors') is True:
                print('Error Code: %s' % str(
                    response.transactionResponse.errors.error[0].errorCode))
                print('Error message: %s' %
                      response.transactionResponse.errors.error[0].errorText)
            else:
                print('Error Code: %s' %
                      response.messages.message[0]['code'].text)
                print('Error message: %s' %
                      response.messages.message[0]['text'].text)
    else:
        print('Null Response.')

    res = debit_bank_account(amount)
    if res is None:
        return render_template('PaymentResponse.html',err = True,msg = "Transaction is Unsuccessful")
    else:
        return render_template('PaymentResponse.html', err = False, msg=res)


"""
Debit a bank account
"""

import random


def debit_bank_account(amount):
    """
    Debit a bank account
    """

    # Create a merchantAuthenticationType object with authentication details
    # retrieved from the constants file
    merchantAuth = apicontractsv1.merchantAuthenticationType()
    merchantAuth.name = CONSTANTS.apiLoginId
    merchantAuth.transactionKey = CONSTANTS.transactionKey

    # Create the payment data for a bank account
    bankAccount = apicontractsv1.bankAccountType()
    accountType = apicontractsv1.bankAccountTypeEnum
    bankAccount.accountType = accountType.checking
    bankAccount.routingNumber = "121042882"
    bankAccount.accountNumber = str(random.randint(10000, 999999999999))
    bankAccount.nameOnAccount = "John Doe"

    # Add the payment data to a paymentType object
    payment = apicontractsv1.paymentType()
    payment.bankAccount = bankAccount

    # Create order information
    order = apicontractsv1.orderType()
    order.invoiceNumber = "10101"
    order.description = "Golf Shirts"

    # Set the customer's Bill To address
    customerAddress = apicontractsv1.customerAddressType()
    customerAddress.firstName = "Ellen"
    customerAddress.lastName = "Johnson"
    customerAddress.company = "Souveniropolis"
    customerAddress.address = "14 Main Street"
    customerAddress.city = "Pecan Springs"
    customerAddress.state = "TX"
    customerAddress.zip = "44628"
    customerAddress.country = "USA"

    # Set the customer's identifying information
    customerData = apicontractsv1.customerDataType()
    customerData.type = "individual"
    customerData.id = "99999456654"
    customerData.email = "EllenJohnson@example.com"

    # Add values for transaction settings
    duplicateWindowSetting = apicontractsv1.settingType()
    duplicateWindowSetting.settingName = "duplicateWindow"
    duplicateWindowSetting.settingValue = "60"
    settings = apicontractsv1.ArrayOfSetting()
    settings.setting.append(duplicateWindowSetting)

    # setup individual line items
    line_item_1 = apicontractsv1.lineItemType()
    line_item_1.itemId = "12345"
    line_item_1.name = "first"
    line_item_1.description = "Here's the first line item"
    line_item_1.quantity = "2"
    line_item_1.unitPrice = "12.95"
    line_item_2 = apicontractsv1.lineItemType()
    line_item_2.itemId = "67890"
    line_item_2.name = "second"
    line_item_2.description = "Here's the second line item"
    line_item_2.quantity = "3"
    line_item_2.unitPrice = "7.95"

    # build the array of line items
    line_items = apicontractsv1.ArrayOfLineItem()
    line_items.lineItem.append(line_item_1)
    line_items.lineItem.append(line_item_2)

    # Create a transactionRequestType object and add the previous objects to it.
    transactionrequest = apicontractsv1.transactionRequestType()
    transactionrequest.transactionType = "authCaptureTransaction"
    transactionrequest.amount = amount
    transactionrequest.payment = payment
    transactionrequest.order = order
    transactionrequest.billTo = customerAddress
    transactionrequest.customer = customerData
    transactionrequest.transactionSettings = settings
    transactionrequest.lineItems = line_items

    # Assemble the complete transaction request
    createtransactionrequest = apicontractsv1.createTransactionRequest()
    createtransactionrequest.merchantAuthentication = merchantAuth
    createtransactionrequest.refId = "MerchantID-0001"
    createtransactionrequest.transactionRequest = transactionrequest
    # Create the controller
    createtransactioncontroller = createTransactionController(
        createtransactionrequest)
    createtransactioncontroller.execute()

    response = createtransactioncontroller.getresponse()

    if response is not None:
        # Check to see if the API request was successfully received and acted upon
        if response.messages.resultCode == "Ok":
            # Since the API request was successful, look for a transaction response
            # and parse it to display the results of authorizing the card
            if hasattr(response.transactionResponse, 'messages') is True:
                print(
                    'Successfully created transaction with Transaction ID: %s'
                    % response.transactionResponse.transId)
                print('Transaction Response Code: %s' %
                      response.transactionResponse.responseCode)
                return response.transactionResponse.transId
                print('Message Code: %s' %
                      response.transactionResponse.messages.message[0].code)
                print('Description: %s' % response.transactionResponse.
                      messages.message[0].description)
            else:
                print('Failed Transaction.')
                if hasattr(response.transactionResponse, 'errors') is True:
                    print('Error Code:  %s' % str(response.transactionResponse.
                                                  errors.error[0].errorCode))
                    print(
                        'Error message: %s' %
                        response.transactionResponse.errors.error[0].errorText)
        # Or, print errors if the API request wasn't successful
        else:
            print('Failed Transaction.')
            if hasattr(response, 'transactionResponse') is True and hasattr(
                    response.transactionResponse, 'errors') is True:
                print('Error Code: %s' % str(
                    response.transactionResponse.errors.error[0].errorCode))
                print('Error message: %s' %
                      response.transactionResponse.errors.error[0].errorText)
            else:
                print('Error Code: %s' %
                      response.messages.message[0]['code'].text)
                print('Error message: %s' %
                      response.messages.message[0]['text'].text)
    else:
        print('Null Response.')

    return None


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
