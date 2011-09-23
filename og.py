import datetime
import os
import sqlite3
import urllib

from flask import Flask, g, redirect, render_template, request
import models

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'og.db')
START_DATE = datetime.date(2011, 8, 1)

app = Flask(__name__)

# template stuff

@app.template_filter('currency')
def currency_filter(f):
    return "$%0.2f" % f

@app.template_filter('urlencode')
def urlencode_filter(s):
    return urllib.quote_plus(s)

# request lifecycle

@app.before_request
def before_request():
    g.db = sqlite3.connect(DB_PATH)

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'db'):
        g.db.close()

# views

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/elections")
@app.route("/elections/<year>")
def election_redirect(year=None):
    return redirect('/elections/2011/council')

@app.route("/elections/<year>/<seat>")
def candidate_list(year, seat):

    if seat != 'council':
        return election_redirect()

    candidates = models.Candidate.list(year, seat)
    return render_template('candidate_list.html', candidates=candidates)

@app.route("/elections/<year>/<seat>/<slug>")
def candidate_detail(year, seat, slug):
    c = models.Candidate(slug)
    timeline = c.timeline(START_DATE)
    in_kind = c.in_kind()
    contributors = c.contributors()
    contribution_types = c.contribution_types()
    return render_template('candidate_detail.html',
                           year=year,
                           candidate=c,
                           contributors=contributors,
                           contribution_types=contribution_types,
                           timeline=timeline,
                           in_kind=in_kind)

@app.route("/elections/contributions")
def contribution_list():

    valid_filters = ('year','seat','contributor','description')

    keys = ('year','candidate','candidate_id','slug','seat','contributor','amount','is_inkind','description','transaction_date')
    stmt = """SELECT %s FROM contributions JOIN candidates ON contributions.candidate_id = candidates.id """ % ", ".join(keys)

    cursor = g.db.cursor()

    where = []
    params = []

    filters = [item for item in request.args.iteritems() if item[0] in valid_filters]

    if filters:

        stmt += "WHERE "

        for col, value in filters:

            if col == 'year' or col == 'seat':
                where.append("%s = ?" % col)
                params.append(value)
            else:
                where.append("%s like ?" % col)
                params.append('%%%s%%' % value)

        stmt += " AND ".join(where)

    stmt += " ORDER BY transaction_date, amount"

    cursor.execute(stmt, params)
    contribs = [dict(zip(keys, row)) for row in cursor]
    cursor.close()

    return render_template('contribution_list.html', contributions=contribs)

if __name__ == "__main__":
    app.run(debug=True, port=8000)