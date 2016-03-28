#!/usr/bin/env python2.7

"""
Columbia W4111 Intro to databases
NAME: Yu Wang  Yuchen Shi
UNI: yw2783 ys2784

Project application:
The project is an online bank application which supports operations like transfer, check statements, look up transactions, etc.
It also supports administrative operations such as add an account in a specific branch. 
This file is server file and mainly responsible for database connection and sql execution.

How to run:

    python server.py

Go to http://localhost:8111 in your browser


"""

import os, json
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, url_for, render_template, g, redirect, Response, session
import traceback

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)


#
# XXX: The URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@w4111db.eastus.cloudapp.azure.com/username
#
# For example, if you had username ewu2493, password foobar, then the following line would be:
#
#     DATABASEURI = "postgresql://ewu2493:foobar@w4111db.eastus.cloudapp.azure.com/ewu2493"
#
#DATABASEURI = "sqlite:///test.db"

#Connect to our database build in project part 1 and 2
DATABASEURI = "postgresql://ys2874:WHPMPK@w4111db.eastus.cloudapp.azure.com/ys2874"

#
# This line creates a database engine that knows how to connect to the URI above
#
engine = create_engine(DATABASEURI)


#
# START SQLITE SETUP CODE
#
# after these statements run, you should see a file test.db in your webserver/ directory
# this is a sqlite database that you can query like psql typing in the shell command line:
# 
#     sqlite3 test.db
#
# The following sqlite3 commands may be useful:
# 
#     .tables               -- will list the tables in the database
#     .schema <tablename>   -- print CREATE TABLE statement for table
# 
# The setup code should be deleted once you switch to using the Part 2 postgresql database
#
#engine.execute("""DROP TABLE IF EXISTS test;""")
#engine.execute("""CREATE TABLE IF NOT EXISTS test (
#  id serial,
#  name text
#);""")
#engine.execute("""INSERT INTO test(name) VALUES ('grace hopper'), ('alan turing'), ('ada lovelace');""")
#
# END SQLITE SETUP CODE
#



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

  # DEBUG: this is debugging code to see what request looks like
  #
  # Flask uses Jinja templates, which is an extension to HTML where you can
  # pass data to a template and dynamically generate HTML based on the data
  # (you can think of it as simple PHP)
  # documentation: https://realpython.com/blog/python/primer-on-jinja-templating/
  #
  # You can see an example template in templates/index.html
  #
  # context are the variables that are passed to the template.
  # for example, "data" key in the context variable defined below will be 
  # accessible as a variable in index.html:
  #
  #     # will print: [u'grace hopper', u'alan turing', u'ada lovelace']
  #     <div>{{data}}</div>
  #     
  #     # creates a <div> tag for each element in data
  #     # will print: 
  #     #
  #     #   <div>grace hopper</div>
  #     #   <div>alan turing</div>
  #     #   <div>ada lovelace</div>
  #     #
  #     {% for n in data %}
  #     <div>{{n}}</div>
  #     {% endfor %}
  #
  #

#
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

@app.route('/statement_lookup', methods=['POST'])
def statement_lookup():
    if session['usertype'] != 'customer':
        return json.dumps({'ec':400, 'em':'notlogin'})
    if 'userid' in session and 'username' in session:
        cid = session['userid']
        name = session['username']
        date_beg = request.form['from']
        date_end = request.form['to']
        try:
            cursor = g.conn.execute("SELECT sid, time_period, begin_balance, end_balance FROM Statements WHERE cid = %s AND time_period BETWEEN %s AND %s", cid, date_beg, date_end)
            statments = []
            for result in cursor:
                statments.append([
                    result[0],
                    result[1],
                    result[2],
                    result[3],
                ])
            cursor.close()
            res_data = {'ec':200, 'em':'success', 'result': statements}
            return json.dumps(res_data)
        except:
            traceback.print_exc()
            return json.dumps({'ec':404, 'em':'dataerror'})
    else:
        return json.dumps({'ec':400, 'em':'notlogin'})

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

@app.route('/transfertrade', methods=['POST'])
def transfertrade():
    if session['usertype'] != 'customer':
        return json.dumps({'ec':400, 'em':'notlogin'})
    if 'userid' in session and 'username' in session:
        cid = session['userid']
        name = session['username']
        target = request.form['target']
        amount = float(request.form['amount'])
        today_date = datetime.datetime.strftime('%Y-%m-%d')
        
        try:
            g.conn.execute("INSERT INTO transactions (amount, date, description, payee) values (?,?,?,?) ", [str(0 - amount), today_date, 'transfer', cid])
            g.conn.commit()

            source_balance = None
            source_acc_no = None
            cursor = g.conn.execute("SELECT acc_no, balance FROM debit_accounts WHERE cid = %s", cid)
            for result in cursor:
                source_acc_no = result[0]
                source_balance = result[1]
            cursor.close()
            target_balance = None
            target_acc_no = None
            cursor = g.conn.execute("SELECT acc_no, balance FROM debit_accounts WHERE cid = %s", target)
            for result in cursor:
                target_acc_no = result[0]
                target_balance = result[1]
            cursor.close()
            if not (target_balance and target_acc_no):
                return json.dumps({'ec':405, 'em':'target no exist'})
            if not (source_balance and tsource_acc_no):
                return json.dumps({'ec':405, 'em':'account not valid'})
            if (float(source_balance) - amount) < 0:
                return json.dumps({'ec':407, 'em':'no enough money'})
            try:
                g.conn.execute("UPDATE  debit_accounts SET balance = (balance + %s) WHERE acc_no = %s", str(amount), target_acc_no)
                g.conn.commit()
                g.conn.execute("UPDATE  debit_accounts SET balance = (balance - %s) WHERE acc_no = %s", str(amount), source_acc_no)
                g.conn.commit()
                res_data = {'ec':200, 'em':'success', 'result': statements}
                return json.dumps(res_data)
            except:
                return json.dumps({'ec':409, 'em':'write error'})
        except:
            traceback.print_exc()
            return json.dumps({'ec':404, 'em':'dataerror'})
    else:
        return json.dumps({'ec':400, 'em':'notlogin'})

 
@app.route('/profile')
def profile():
    if session['usertype'] != 'customer':
        return render_template('index.html')
    if 'userid' in session and 'username' in session:
        cid = session['userid']
        name = session['username']
        cursor = g.conn.execute("SELECT email, phone, ssn FROM Customers WHERE cid = %s", cid)
        for result in cursor:
            email = result[0]
            phone = result[1]
            ssn = result[2]
        return render_template("profile.html", customer = {'name':name},  profile={'name':name, 'email':email, 'phone':phone, 'ssn':ssn})
    else:
        return render_template('index.html')

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
            g.conn.execute("UPDATE  customers SET name = %s, email = %s, phone = %s, ssn = %s, password = %s WHERE acc_no = %s", update_name, update_email, update_phone, update_ssn, update_password)
            g.conn.commit()
        except:
            return {'ec':402, 'em':'update error'}
    else:
        return {'ec':400, 'em':'nologin'}


@app.route('/admin')
def admin():
    if session['usertype'] != 'admin':
        return render_template('index.html')
    if 'userid' in session and 'username' in session:
        branch = None
        customer = None
        transaction = None
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
        
        return render_template("admin.html", branch=branch, customer=customer, transaction=transaction)
    else:
        return render_template('index.html')

@app.route('/branch')
def branch():
    if session['usertype'] != 'admin':
        return render_template('index.html')
    if 'userid' in session and 'username' in session:
        return render_template("branch.html")
    else:
        return render_template('index.html')

@app.route('/branch_lookup', methods=['POST'])
def branch_lookup():
    if session['usertype'] != 'admin':
        return {'ec':400, 'em':'nologin'}
    if 'userid' in session and 'username' in session:
        branchid = request.form['branch_id']
        branchname = request.form['branch_name']
        where_sentence = ''
        if branchid:
            where_sentence = 'WHERE branch_id=%s'% (branchid)
        elif branchname:
            where_sentence = 'WHERE name LIKE %s' ('%' + branchname +'%')
        try:
            cursor = g.conn.execute("SELECT branch_id, name, address, bid FROM branches %s", where_sentence)
            branches = []
            for result in cursor:
                branches.append([
                    result[0],
                    result[1],
                    result[2],
                    result[3],
                ])
            cursor.close()
            res_data = {'ec':200, 'em':'success', 'result': branches}
            return json.dumps(res_data)
        except:
            traceback.print_exc()
            return json.dumps({'ec':404, 'em':'dataerror'})
    else:
        return {'ec':400, 'em':'nologin'}


  #name = request.form['name']
  #cursor = g.conn.execute('select * from branch where name = %s or name like %s\%', name)
  #names = []
  #for result in cursor:
  #  names.append(result[1])  # can also be accessed using result[0]
  #cursor.close()


@app.route('/addnew')
def addnew():
    if session['usertype'] != 'admin':
        return render_template('index.html')
    if 'userid' in session and 'username' in session:
        return render_template("addnew.html")
    else:
        return render_template('index.html')

@app.route('/addcustomer', methods=['POST'])
def addcustomer():
    if session['usertype'] != 'admin':
        return json.dumps({'ec':400, 'em':'nologin'})
    if 'userid' in session and 'username' in session:
        new_name = request.form['name']
        new_email = request.form['email']
        new_phone = request.form['phone']
        new_ssn = request.form['ssn']
        new_password = request.form['password']
        try:
            g.conn.execute("INSERT INTO customers (name, email, phone, ssn, password) values (?,?,?,?,?) ", [new_name, new_email, new_phone, new_ssn, new_password])
            g.conn.commit()
            return json.dumps( {'ec':200, 'em':'success'})
        except:
            return json.dumps( {'ec':404, 'em':'data writing error'})
    else:
        return json.dumps({'ec':400, 'em':'nologin'})

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
            where_sentence = 'WHERE cid=%s'% (customerid)
        elif customername:
            where_sentence = 'WHERE name LIKE %s' ('%' + customername +'%')
        try:
            cursor = g.conn.execute("SELECT cid, name, email, phone, ssn FROM branches %s", where_sentence)
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
        where_sentence = "WHERE date BETWEEN %s AND %s" %(date_beg, date_end)
        if transaction_type:
            where_sentence += 'AND description = %s' %(transaction_type)
        try:
            cursor = g.conn.execute("SELECT tran_no, amount, date, description, payee FROM transactions %s", where_sentence)
            transactiones = []
            for result in cursor:
                transactiones.append([
                    result[0],
                    result[1],
                    result[2],
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



# Example of adding new data to the database
#@app.route('/add', methods=['POST'])
#def add():
#  name = request.form['name']
#  g.conn.execute('INSERT INTO test VALUES (NULL, ?)', name)
#  return redirect('/')

#User login validation
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

# Main funciton

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
