import requests
import sys
import urllib.parse
from flask import redirect, jsonify, render_template, request, session
from functools import wraps


# inserts API in main application code
def get_key():
    return '' # insert API key here


# check user is logged in
def is_logged_in(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/log_reg")
        return f(*args, **kwargs)
    return decorated_function


# search function
def booksearch(query, refineQuery = "", refine = ""):

    # regular search code
    if not refine and not refineQuery:

        searchdata = {'q': urllib.parse.quote_plus(query), 'filter':'free-ebooks', 'maxResults' : '10', 'key':get_key()}

        try:
            response = requests.get("https://www.googleapis.com/books/v1/volumes", params=searchdata)
            response.raise_for_status()
        except requests.RequestException:
            return None

    # refined search code
    else:
        # if new query not entered, use previous query
        if not refineQuery:
            refineQuery = query
        elif not refine:
            return error("You must select a catagory to refine", 403)

        # resend request to API with updated filters
        newData = '+' + refine + ':' + urllib.parse.quote_plus(refineQuery)
        searchdata = {'filter':'free-ebooks', 'q': urllib.parse.quote_plus(query) + newData, 'maxResults' : '40', 'key':get_key()}

        try:
            response = requests.get("https://www.googleapis.com/books/v1/volumes", params=searchdata)
            response.raise_for_status()
        except requests.RequestException:
            return None

    # check results found
    if int(response.json()['totalItems']) > 0:
        try:
            response = response.json()['items']
            results = []

            for book in response:
                newBook = getBookInfo(book['id'])
                results.append(newBook)
            return results

        except (KeyError, ValueError):
            return None

    else:
        return None


# renders error message to screen
def error(message, errorCode):
    return render_template("error.html", message=message, errorCode=errorCode)

# returns a book dictionary based on bookId
def getBookInfo(bookId):
    newBook = {}
    # call API
    try:
        response = requests.get("https://www.googleapis.com/books/v1/volumes/"+bookId+"?key="+get_key())
        response.raise_for_status()
    except requests.RequestException:
        return None

    # create values in dictionary: newBook
    try:
        response = response.json()
        volume = response['volumeInfo']
        bookData = ['title', 'authors', 'id', 'publisher', 'publishedDate', 'description', 'imageLinks']

        # attempt to store each key value and ignore key error exceptions
        for datum in bookData:
            try:
                if datum == 'id':
                    newBook['bookId'] = response[datum]
                elif datum == 'authors':
                    newBook[datum] = ", ".join(volume[datum])
                elif datum == 'imageLinks':
                    newBook[datum] = {}
                    try:
                        newBook[datum]['thumbnail'] = volume[datum]['thumbnail']
                    except (KeyError):
                        newBook[datum]['thumbnail'] = "https://via.placeholder.com/150x200.png?text=No+image+available"
                    try:
                        newBook[datum]['small'] = volume[datum]['small']
                    except (KeyError):
                        pass
                    except (KeyError):
                        pass
                else:
                    newBook[datum] = volume[datum]
            except (KeyError):
                pass
        return newBook

    except (KeyError, TypeError, ValueError):
        return None

