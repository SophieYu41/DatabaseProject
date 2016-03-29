#!/usr/bin/env python2.7

"""
Columbia W4111 Intro to databases
Author: Yu Wang 

Project application:
The project is an online bank application which supports operations like transfer, check statements, look up transactions, etc.
It also supports administrative operations such as add an account in a specific branch. 
This file is server file and mainly responsible for database connection and sql execution.

How to run:

    python server.py

Go to http://localhost:8111 in your browser


"""

import os, json, datetime, time, random
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, url_for, render_template, g, redirect, Response, session
import traceback

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)


#Connect to our database build in project part 1 and 2
DATABASEURI = "postgresql://ys2874:WHPMPK@w4111db.eastus.cloudapp.azure.com/ys2874"

#
# This line creates a database engine that knows how to connect to the URI above
#
engine = create_engine(DATABASEURI)


@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request 
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request

  The variable g is globally accessible
  """
  try:
    g.conn = engine.connect()
  except:
    print "uh oh, problem connecting to database"
    g.conn = None

@app.teardown_request
def teardown_request(exception):
  """
  At the end of the web request, this makes sure to close the database connection.
  If you don't the database could run out of memory!
  """
  try:
    g.conn.close()
  except Exception as e:
    pass


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to e.g., localhost:8111/foobar/ with POST or GET then you could use
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: http://flask.pocoo.org/docs/0.10/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#

#
# This part validate user login information and check if the session is still valid
#

@app.route('/')
def index():
    """
    request is a special object that Flask provides to access web request information:

    request.method:   "GET" or "POST"
    request.form:     if the browser submitted a form, this contains the data in the form
    request.args:     dictionary of URL arguments e.g., {a:1, b:2} for http://localhost?a=1&b=2

    See its API: http://flask.pocoo.org/docs/0.10/api/#incoming-request-data
    """
    if ('username' in session) and ('usertype' in session):
        if session['usertype'] == 'admin':
            return redirect(url_for('admin'))
        elif session['usertype'] == 'customer':
            return redirect(url_for('customer'))
    else:
        return render_template('index.html')


"""
Customer MODULE

"""

#
# SQL for customer page
# display the debit account_no and current balance
#

@app.route('/customer')
def customer():
    cid = session['userid']
    name = session['username']
    accounts = []
    try:
        cursor = g.conn.execute("SELECT debit_no, balance FROM Debit_Accounts WHERE cid = %s", cid)
        for result in cursor:
            accounts.append({
                'num':result[0], 
                'balance': str(result[1])
            })
    except:
        traceback.print_exc()
    return render_template("customer.html", customer = {'name':name}, accounts = accounts)
    #return render_template("customer_layout.html", final_res)

# Sub-page for user statement
# redirect user to statement page when subpage is selected

@app.route('/statement')
def statement(begdate=None, enddate=None):
    if session['usertype'] != 'customer':
        return redirect(url_for("login"))
    if 'userid' in session and 'username' in session:
        cid = session['userid']
        name = session['username']
        return render_template("statement.html", customer = {'name':name})
    else:
        return redirect(url_for("login"))

#
# SQL for statement lookup
# look up for transactions/statements in database related to the account
# 

@app.route('/statement_lookup', methods=['POST'])
def statement_lookup():
    if session['usertype'] != 'customer':
        return json.dumps({'ec':400, 'em':'notlogin'})
    if 'userid' in session and 'username' in session:
        cid = session['userid']
        name = session['username']
        try:
           # cursor = g.conn.execute("SELECT sid, time_period, begin_balance, end_balance FROM Statements WHERE cid = %s ", cid)
           # statements = []
           # for result in cursor:
           #     statements.append([
           #         result[0],
           #         result[1],
           #         result[2],
           #         result[3],
           #     ])
            cursor = g.conn.execute("select name, transactions.tran_no, amount, date, description, payee from customers, debit_owns, debit_conducts, transactions where customers.cid=debit_owns.cid and debit_owns.debit_no=debit_conducts.debit_no and debit_conducts.tran_no=transactions.tran_no and customers.cid=%s", cid)
	    statements = []
            for result in cursor:
                statements.append([
                    result[0],
                    result[1],
                    result[2],
                    result[3].strftime('%Y-%m-%d'),
                    result[4],
                    result[5],
                ])
	    cursor.close()
            res_data = {'ec':200, 'em':'success', 'result': statements}
            return json.dumps(res_data)
        except:
            traceback.print_exc()
            return json.dumps({'ec':404, 'em':'dataerror'})
    else:
        return json.dumps({'ec':400, 'em':'notlogin'})

# Sub-page for transfer money page
# redirect user to transfer money page page when subpage is selected

@app.route('/transfer')
def transfer():
    if session['usertype'] != 'customer':
        return redirect(url_for("login"))
    if 'userid' in session and 'username' in session:
        cid = session['userid']
        name = session['username']
        return render_template("transfer.html", customer = {'name':name})
    else:
        return redirect(url_for("login"))

#
# SQL for transfer transaction
#   1. modify customer balance for both accounts related
#   2. Insert new record in transaction table
# 

@app.route('/transfertrade', methods=['POST'])
def transfertrade():
    if session['usertype'] != 'customer':
        return json.dumps({'ec':400, 'em':'notlogin'})
    if 'userid' in session and 'username' in session:
        try:
            cid = session['userid']
            name = session['username']
            target = request.form['target']
	    print 'transfer',target
            amount = float(request.form['amount'])
            today_date = datetime.datetime.today().strftime('%Y-%m-%d')
            trade_no = cid.split('_')[0] + str(int(time.time())) + str(random.randrange(1000, 9999))
            g.conn.execute("INSERT INTO transactions (tran_no, amount, date, description, payee) values (%s, %s, %s, %s, %s) ", trade_no, 0 - amount, today_date, 'transfer', cid)
            source_balance = None
            source_debit_no = None
            cursor = g.conn.execute("SELECT debit_no, balance FROM debit_accounts WHERE cid = %s", cid)
            for result in cursor:
                source_debit_no = result[0]
                source_balance = result[1]
            cursor.close()
            target_balance = None
            target_debit_no = None
            cursor = g.conn.execute("SELECT debit_no, balance FROM debit_accounts WHERE debit_no = %s", target)
            for result in cursor:
                target_debit_no = result[0]
                target_balance = result[1]
            cursor.close()
            if not (target_balance and target_debit_no):
                return json.dumps({'ec':405, 'em':'target no exist'})
            if not (source_balance and source_debit_no):
                return json.dumps({'ec':405, 'em':'account not valid'})
            if (float(source_balance) - amount) < 0:
                return json.dumps({'ec':407, 'em':'no enough money'})
            try:
                g.conn.execute("UPDATE  debit_accounts SET balance = (balance + %s) WHERE debit_no = %s", str(amount), target_debit_no)
                g.conn.execute("UPDATE  debit_accounts SET balance = (balance - %s) WHERE debit_no = %s", str(amount), source_debit_no)
                res_data = {'ec':200, 'em':'success'}
                return json.dumps(res_data)
            except:
                traceback.print_exc()
                return json.dumps({'ec':409, 'em':'write error'})
        except:
            traceback.print_exc()
            return json.dumps({'ec':404, 'em':'dataerror'})
    else:
        return json.dumps({'ec':400, 'em':'notlogin'})

# Sub-page for customer profile page
# redirect user to profile page when subpage is selected

@app.route('/profile')
def profile():
    if session['usertype'] != 'customer':
        return render_template('index.html')
    if 'userid' in session and 'username' in session:
        cid = session['userid']
        name = session['username']
        cursor = g.conn.execute("SELECT email, phone, ssn, password FROM Customers WHERE cid = %s", cid)
        for result in cursor:
            email = result[0]
            phone = result[1]
            ssn = result[2]
            password = result[3]
        return render_template("profile.html", customer = {'name':name},  profile={'name':name, 'email':email, 'phone':phone, 'ssn':ssn, 'password':password})
    else:
        return render_template('index.html')
#
# SQL for transfer transaction
# update user information according to user input
#

@app.route('/profileedit', methods=['POST'])
def profileedit():
    if session['usertype'] != 'customer':
        return {'ec':400, 'em':'nologin'}
    if 'userid' in session and 'username' in session:
        cid = session['userid']
        name = session['username']
        update_name = request.form['name']
        update_email = request.form['email']
        update_phone = request.form['phone']
        update_ssn = request.form['ssn']
        update_password = request.form['password']
        try:
            g.conn.execute("UPDATE  customers SET name = %s, email = %s, phone = %s, ssn = %s, password = %s WHERE cid = %s", update_name, update_email, update_phone, update_ssn, update_password, cid)
        except:
            traceback.print_exc()
            return {'ec':402, 'em':'update error'}
    else:
        return {'ec':400, 'em':'nologin'}

"""
ADMIN MODULE
"""

#
# SQL for admin page
# display the aggregation information for currentdatabase
#   1. total number of branch
#   2. total number of customers
#   3. total number of transactions
#   4. list the most valuable customer--customer with the most number of transactions
#

@app.route('/admin')
def admin():
    if session['usertype'] != 'admin':
        return render_template('index.html')
    if 'userid' in session and 'username' in session:
        branch = None
        customer = None
        transaction = None
	valuableCus= None
        cursour = g.conn.execute("SELECT COUNT(DISTINCT branch_id) FROM branches")
        for c in cursour:
            branch = c[0]
        cursour.close()
        cursour = g.conn.execute("SELECT COUNT(DISTINCT cid) FROM customers")
        for c in cursour:
            customer = c[0]
        cursour.close()
        cursour = g.conn.execute("SELECT COUNT(DISTINCT tran_no) FROM Transactions")
        for c in cursour:
            transaction = c[0]
        cursour.close()
	cursour = g.conn.execute("select name from Customers,debit_owns d where d.cid = Customers.cid and d.debit_no IN (select temp.debit_no from (select count(debit_no),debit_no from debit_conducts group by debit_no order by count DESC) temp limit 1 );") 
        for c in cursour:
             valuableCus = c[0]
        cursour.close()  
      
        return render_template("admin.html", branch=branch, customer=customer, transaction=transaction, valuableCus=valuableCus)
    else:
        return render_template('index.html')

# Sub-page for admin branch page
# redirect to branch page when subpage is selected

@app.route('/branch')
def branch():
    if session['usertype'] != 'admin':
        return render_template('index.html')
    if 'userid' in session and 'username' in session:
        return render_template("branch.html")
    else:
        return render_template('index.html')

#
# SQL for branch lookup page
# display the branch information according to either branch_id or branch_name
# 

@app.route('/branch_lookup', methods=['POST'])
def branch_lookup():
    if session['usertype'] != 'admin':
        return {'ec':400, 'em':'nologin'}
    if 'userid' in session and 'username' in session:
        branchid = request.form['branch_id']
        branchname = request.form['branch_name']
        where_sentence = ''
        if branchid:
            where_sentence = "WHERE branch_id='%s'"% (branchid)
        elif branchname:
            where_sentence = "WHERE name LIKE %s" %("'%%" + branchname +"%%'")
        try:
            print 'SQL:________'
            sql = '''
                SELECT branch_id, name, address FROM branches %s
            ''' %(where_sentence)
            print sql
            cursor = g.conn.execute(sql)
            branches = []
            for result in cursor:
                branches.append([
                    result[0],
                    result[1],
                    result[2],
                ])
            cursor.close()
            res_data = {'ec':200, 'em':'success', 'result': branches}
            return json.dumps(res_data)
        except:
            traceback.print_exc()
            return json.dumps({'ec':404, 'em':'dataerror'})
    else:
        return {'ec':400, 'em':'nologin'}


# Sub-page for admin adding a new customer
# redirect to add-new-customer page when subpage is selected

@app.route('/addnew')
def addnew():
    if session['usertype'] != 'admin':
        return render_template('index.html')
    if 'userid' in session and 'username' in session:
        return render_template("addnew.html")
    else:
        return render_template('index.html')


#
# SQL for add new customer page
# insert into Customer table with the parameter from input
# 

@app.route('/addcustomer', methods=['POST'])
def addcustomer():
    if session['usertype'] != 'admin':
        return json.dumps({'ec':400, 'em':'nologin'})
    if 'userid' in session and 'username' in session:
        new_cid = request.form['cid']
        new_name = request.form['name']
        new_email = request.form['email']
        new_phone = request.form['phone']
        new_ssn = request.form['ssn']
        new_password = request.form['password']
        print new_cid
        print new_name
        print new_email
        print new_phone
        print new_ssn
        print new_password
        try:
            sql = '''
                INSERT INTO customers (cid, name, email, phone, ssn, password) values ('%s', '%s','%s','%s','%s','%s') 
            ''' %(str(new_cid), str(new_name), str(new_email), str(new_phone), str(new_ssn), str(new_password))
            print 'SQL:------'
            print sql
            g.conn.execute(sql)
            return json.dumps( {'ec':200, 'em':'success'})
        except:
            traceback.print_exc()
            return json.dumps( {'ec':404, 'em':'data writing error'})
    else:
        return json.dumps({'ec':400, 'em':'nologin'})

#
# Subpage and SQL for search customer page
# display corresponding customer information according to input parameter
# 

@app.route('/searchcustomer')
def searchcustomer():
    return render_template("searchcustomer.html")

@app.route('/customer_lookup', methods=['POST'])
def customer_lookup():
    if session['usertype'] != 'admin':
        return render_template('index.html')
    if 'userid' in session and 'username' in session:
        customerid = request.form['customer_id']
        customername = request.form['customer_name']
        where_sentence = ''
        if customerid:
            where_sentence = "WHERE cid='%s'"% (customerid)
        elif customername:
            where_sentence = "WHERE name LIKE %s" % ("'%%" + customername +"%%'")
        try:
            cursor = g.conn.execute("SELECT cid, name, email, phone, ssn FROM Customers " + where_sentence)
            customers = []
            for result in cursor:
                customers.append([
                    result[0],
                    result[1],
                    result[2],
                    result[3],
                    result[4],
                ])
            cursor.close()
            res_data = {'ec':200, 'em':'success', 'result': customers}
            return json.dumps(res_data)
        except:
            traceback.print_exc()
            return json.dumps({'ec':404, 'em':'dataerror'})
    else:
        return {'ec':400, 'em':'nologin'}

#
# Subpage and SQL for transaction page
# display corresponding transaction information
# Input could either be date, transaction type  or description
#

@app.route('/transaction')
def transaction(begdate=None, enddate=None):
    if session['usertype'] != 'admin':
        return redirect(url_for("login"))
    if 'userid' in session and 'username' in session:
        return render_template("transaction.html")
    else:
        return redirect(url_for("login"))

@app.route('/transaction_lookup', methods=['POST'])
def transaction_lookup():
    if session['usertype'] != 'admin':
        return json.dumps({'ec':400, 'em':'notlogin'})
    if 'userid' in session and 'username' in session:
        cid = session['userid']
        name = session['username']
        date_beg = request.form['from']
        date_end = request.form['to']
        transaction_type = request.form['type']
        where_sentence = 'WHERE'
	#if query by date

        if date_beg and date_end:
            try:
                date_beg = datetime.datetime.strptime(date_beg, '%Y-%m-%d').strftime('%Y-%m-%d')
                date_end = datetime.datetime.strptime(date_end, '%Y-%m-%d').strftime('%Y-%m-%d')
            except:
                traceback.print_exc()
                return json.dumps({'ec':405, 'em':'datetime format wrong: YYYY-mm-dd'})
            where_sentence += " date BETWEEN '%s' AND '%s'" %(min(str(date_beg), str(date_end)), max(str(date_beg), str(date_end)))

            #if query by transaction type
            if transaction_type:
                where_sentence += " AND description = '%s'" %(transaction_type)
        elif transaction_type:
            where_sentence += " description = '%s'" %(transaction_type)
        try:
            if where_sentence == 'WHERE': where_sentence = ''
            cursor = g.conn.execute("SELECT tran_no, amount, date, description, payee FROM transactions " + where_sentence)
            transactiones = []
            for result in cursor:
                transactiones.append([
                    result[0],
                    result[1],
                    result[2].strftime('%Y-%m-%d'),
                    result[3],
                    result[4],
                ])
            cursor.close()
            res_data = {'ec':200, 'em':'success', 'result': transactiones}
            return json.dumps(res_data)
        except:
            traceback.print_exc()
            return json.dumps({'ec':404, 'em':'dataerror'})
    else:
        return json.dumps({'ec':400, 'em':'notlogin'})


#
# User login validation
# Identify user entity, distribu user to their correspoding page
# Admin page or Customer page
#

@app.route('/login', methods=['POST'])
def login():
    post_name = request.form['name']
    post_password = request.form['password']
    password = None
    cid = None
    cursor = g.conn.execute("SELECT cid, password FROM Customers WHERE name = %s", post_name)
    for result in cursor:
        cid = result[0].strip()
        password = result[1].strip()
    cursor.close();
    print post_name, post_password, cid, password
    if password == post_password:
        session['username'] = post_name
        session['userid'] = cid
        if post_name == 'admin':
            session['usertype'] = 'admin'
            return redirect(url_for('admin'))
        else:
            session['usertype'] = 'customer'
            return redirect(url_for('customer'))
    else:
        return json.dumps({'ec':400, 'em':'wrong password or username'})

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('userid', None)
    session.pop('usertype', None)
    return redirect(url_for('index'))

"""
# Main funciton
"""

app.secret_key = 'A0Zrjxj/3yX R~XHH!jwd]LWX/,?RT'

if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        HOST, PORT = host, port
        print "Banking Applicaion System"  
        print "running on %s:%d" % (HOST, PORT)
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)


    run()
