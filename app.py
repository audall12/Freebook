import json

from cs50 import SQL
from datetime import timedelta, datetime
from extras import get_key, booksearch, error, is_logged_in, getBookInfo
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session


from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

# configure application
app = Flask(__name__)

# auto-reload templates
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = datetime.now() + timedelta(200)
    response.headers["Pragma"] = "no-cache"
    return response


# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///freebook.db")


@app.route("/log_reg", methods=['GET', 'POST'])
def log_reg():
    if request.method == "GET":
        return render_template("log_reg.html")
    else:
        # check if logging in or registering
        if 'login' in request.form:

            logUser = request.form.get('logUser').lower()
            logPass = request.form.get('logPass')

            # check fields have been filled
            if not logUser or not logPass:
                return error("Please fill in required fields", 403)

            # check username and password in database
            userdata = db.execute('SELECT * FROM users WHERE username = :username', username = logUser)

            if len(userdata) != 1 or not check_password_hash(userdata[0]['hash'], logPass):
                return error('Wrong username or password', 403)

            session['user_id'] = userdata[0]['uid']

            return redirect('/')

        elif 'register' in request.form:

            regUser = request.form.get('regUser').lower()
            regPass = request.form.get('regPass')
            regConf = request.form.get('regConf')

            # check fields have been filled
            if not regUser or not regPass or not regConf:
                return error("Please fill in required fields", 403)

            # check username already exists
            userdata = db.execute('SELECT * FROM users WHERE username = :username', username = regUser)
            if len(userdata) == 1:
                return error("Username already taken", 403)

            # check passwords relate
            if regPass != regConf:
                return error("The passwords you enetered do not match", 403)

            # create new user
            db.execute("INSERT INTO users ('username', 'hash') VALUES (:username, :passHash)", username = regUser, passHash = generate_password_hash(regPass))

            # start session with user's user id
            session['user_id'] = db.execute('SELECT uid FROM users WHERE username = :username', username = regUser)

            return redirect('/')

        else:
            return error('buttons dont work', 403)


@app.route("/")
@is_logged_in
def index():
    # get bookcase for shelf
    bookcaseData = db.execute('SELECT * FROM bookcase WHERE uid = :uid', uid = session['user_id'])
    bookcase = []
    for book in bookcaseData:
        newBook = getBookInfo(book['bookId'])
        bookcase.append(newBook)

    # get finished for shelf
    finishedData = db.execute('SELECT * FROM finished WHERE uid = :uid', uid = session['user_id'])
    finished = []
    for book in finishedData:
        newBook = getBookInfo(book['bookId'])
        finished.append(newBook)

    # get first child of reading list
    readingData = db.execute('SELECT * FROM reading WHERE uid = :uid', uid = session['user_id'])

    # check list isn't empty
    if len(readingData) != 0:
        readingBook = getBookInfo(readingData[0]['bookId'])
    else:
        readingBook = None

    return render_template("index.html", bookcase=bookcase, finished=finished, readingBook=readingBook)


@app.route("/logout")
def logout():
    session.clear()
    flash(u"successfully logged out", "alert-success")
    return redirect("/")


@app.route("/search", methods=["GET", "POST"])
@is_logged_in
def search():
    message = "No results found"
    if request.method == "GET":
        # regular search
        query = request.args.get("query")
        results = booksearch(query)

        # check results found, otherwise render message
        if results:
            return render_template("search.html", results=results, query=query, message=message)
        else:
            return render_template("search.html", results="", query=query, message=message)
    else:
        # refined search
        query = request.form.get("query")
        refineQuery = request.form.get("refineQuery")
        refine = request.form.get("refine")
        results = booksearch(query, refineQuery, refine)

        # check results found
        if results:
            return render_template("search.html", results=results, query=query, message=message)
        else:
            return render_template("search.html", results="", query=query, message=message)


@app.route("/reading", methods=['GET'])
@is_logged_in
def reading():
    bookId= request.args.get('bookId')

    if bookId != "": # accessed through hyperlink or button
        firstBook = {}
        firstBook['bookId'] = bookId

        # check book isn't already in reading list under user
        response = db.execute('SELECT * FROM reading WHERE uid = :uid AND bookId = :bookId', uid=session['user_id'], bookId=bookId)

        if len(response) == 0:
            # insert into reading database
            db.execute("INSERT INTO reading ('uid', 'bookId') VALUES (:uid, :bookId)", uid=session['user_id'], bookId=bookId)
            firstBook['page'] = None

        else:
            firstBook['page'] = response[0]['page']

        # create a list of reading books from database
        readingData = db.execute('SELECT * FROM reading WHERE uid = :uid', uid = session['user_id'])
        reading = []

        for book in readingData:
            newBook = getBookInfo(book['bookId'])
            reading.append(newBook)

        return render_template("reading.html", reading=reading, firstBook=firstBook)

    else:  # accessed via navbar
        firstBook = {}

        # create a list of reading books from database
        readingData = db.execute('SELECT * FROM reading WHERE uid = :uid', uid = session['user_id'])
        reading = []

        for book in readingData:
            newBook = getBookInfo(book['bookId'])
            reading.append(newBook)

        try:
            firstBook['bookId'] = readingData[0]['bookId']
            firstBook['page'] = readingData[0]['page']

        except IndexError:
            firstBook = None

        return render_template("reading.html", reading=reading, firstBook=firstBook)


@app.route("/bookcase")
@is_logged_in
def bookcase():
    # get book IDs for bookcase db
    bookcaseData = db.execute("SELECT bookId FROM bookcase WHERE uid = :uid", uid=session['user_id'])
    bookcase=[]

    # iterate through and create object of each book
    for book in bookcaseData:
        newBook = getBookInfo(book['bookId'])
        bookcase.append(newBook)

    # get book IDs for finished list
    finishedData = db.execute("SELECT bookId FROM finished WHERE uid = :uid", uid=session['user_id'])
    finished=[]

    # iterate through and create object of each book
    for book in finishedData:
        newBook = getBookInfo(book['bookId'])
        finished.append(newBook)

    return render_template("bookcase.html", finished=finished, bookcase=bookcase)


@app.route("/settings", methods=["GET", "POST"])
@is_logged_in
def settings():
    if request.method == "GET":
        return render_template("settings.html")

    else:
        # changing password
        if 'change' in request.form:
            pass1 = request.form.get('pass1')
            pass2 = request.form.get('pass2')
            pass3 = request.form.get('pass3')

            # Find password in database
            dataPass = db.execute("SELECT hash FROM users WHERE uid = :uid", uid = session["user_id"])[0]["hash"]

            # check fields are filled
            if not pass1 or not pass2 or not pass3:
                return error('You must fill in all the required fields', 403)

            # check current password is correct
            if not check_password_hash(dataPass, pass1):
                return error('Password incorrect', 403)

            # check new passwords match
            if pass2 != pass3:
                return error('Your new passwords do not match', 403)

            # update database
            db.execute("UPDATE users SET hash = :pass2 WHERE uid = :uid", pass2 = generate_password_hash(pass2), uid = session["user_id"])

            flash(u"Password successfully changed", "alert-success")
            return render_template("settings.html")

        # delete account
        elif 'delete' in request.form:
            # delete all data from users database for user
            db.execute("DELETE FROM users WHERE uid = :uid", uid = session["user_id"])

            # delete all data from bookcase database for user
            db.execute("DELETE FROM bookcase WHERE uid = :uid", uid = session["user_id"])

            # delete all data from finished database for user
            db.execute("DELETE FROM finished WHERE uid = :uid", uid = session["user_id"])

            # delete all data from reading database for user
            db.execute("DELETE FROM reading WHERE uid = :uid", uid = session["user_id"])

            session.clear()
            flash(u"Account deleted", "alert-success")
            return redirect("/")


# adds book to user's bookcase db
@app.route("/appendBookcase")
@is_logged_in
def appendBookcase():
    bookId = request.args.get('bookId')

    # check book isn't already in bookcase or finished list under user
    bookcase = db.execute('SELECT * FROM bookcase WHERE uid = :uid AND bookId = :bookId', uid=session['user_id'], bookId=bookId)
    finished = db.execute('SELECT * FROM finished WHERE uid = :uid AND bookId = :bookId', uid=session['user_id'], bookId=bookId)

    if len(finished) == 1:
        # delete data of bookId and user from finished db
        db.execute('DELETE FROM finished WHERE uid = :uid AND bookId = :bookId', uid=session['user_id'], bookId=bookId)

    if len(bookcase) != 1:
        # insert bookId into database
        db.execute("INSERT INTO bookcase ('uid', 'bookId') VALUES (:uid, :bookId)", uid=session['user_id'], bookId=bookId)
        return jsonify(True)
    else:
        return jsonify(False)


# adds book to user's finished list
@app.route("/appendFinished")
@is_logged_in
def appendFinished():
    bookId = request.args.get('bookId')

    # check book isn't already in bookcase or finished list under user
    bookcase = db.execute('SELECT * FROM bookcase WHERE uid = :uid AND bookId = :bookId', uid=session['user_id'], bookId=bookId)
    finished = db.execute('SELECT * FROM finished WHERE uid = :uid AND bookId = :bookId', uid=session['user_id'], bookId=bookId)

    if len(bookcase) == 1:
        # delete data of bookId and user from bookcase db
        db.execute('DELETE FROM bookcase WHERE uid = :uid AND bookId = :bookId', uid=session['user_id'], bookId=bookId)

    if len(finished) != 1:
        # insert bookId into database
        db.execute("INSERT INTO finished ('uid', 'bookId') VALUES (:uid, :bookId)", uid=session['user_id'], bookId=bookId)
        return jsonify(True)
    else:
        return jsonify(False)


# adds book to user's bookcase db
@app.route("/removeBookcase", methods=['GET'])
@is_logged_in
def removeBookcase():
    bookId = request.args.get('bookId')
    db.execute('DELETE FROM bookcase WHERE uid = :uid AND bookId = :bookId', uid=session['user_id'], bookId=bookId)
    flash(u'Book removed from your Bookcase', "alert-success")
    return redirect('/bookcase')


# adds book to user's finished list
@app.route("/removeFinished", methods=['GET'])
@is_logged_in
def removeFinished():
    bookId = request.args.get('bookId')
    db.execute('DELETE FROM finished WHERE uid = :uid AND bookId = :bookId', uid=session['user_id'], bookId=bookId)
    flash(u'Book removed from your Finished List', "alert-success")
    return redirect('/bookcase')


# update page number in database
@app.route("/updatePage", methods= ["GET"])
@is_logged_in
def updatePage():
    bookId = request.args.get('bookId')
    page = request.args.get('page')

    db.execute("UPDATE reading SET 'page' = :page WHERE 'uid' = :uid AND 'bookId' = :bookId", uid=session['user_id'], bookId=bookId, page=page)
    return jsonify(True)


# check username/password via AJAX
@app.route("/checkUser")
def checkUser():

    user = request.args.get('user')
    form = request.args.get('form')

    userData = db.execute('SELECT * FROM users WHERE username = :username', username=user)

    if form == 'login':
        if len(userData) == 1:
            return jsonify(True)
        return jsonify(False)

    elif form == 'register':
        if len(userData) != 1:
            return jsonify(True)
        return jsonify(False)


@app.route("/checkPass")
def checkPass():
    user = request.args.get('user')
    password = request.args.get('password')
    confirm = request.args.get('confirm')

    passData = db.execute('SELECT hash FROM users WHERE username = :username', username=user)[0]['hash']

    if user:
        if check_password_hash(passData, password):
            return jsonify(True)
        return jsonify(False)
    else:
        if password == confirm & len(password) > 8:
            return jsonify(True)
    return jsonify(False)


@app.route("/pageUpdate")
def pageUpdate():
    page = request.args.get('page')
    bookId = request.args.get('bookId')

    db.execute('UPDATE reading SET page = :page WHERE bookId = :bookId AND uid = :uid', bookId=bookId, uid = session['user_id'], page=page)
    return jsonify(True)

