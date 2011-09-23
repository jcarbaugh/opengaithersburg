import datetime

from flask import g

def parse_date(s):
    return datetime.datetime.strptime(s, "%Y-%m-%d").date()

def date_iter(start_date, end_date):
    days = (end_date - start_date).days
    for i in xrange(days + 1):
        yield start_date + datetime.timedelta(i)

def timeline_iter(data, start_date, end_date, cumulative=False):
    value = 0
    for date in date_iter(start_date, end_date):
        if cumulative:
            value += data.get(date, 0)
        else:
            value = data.get(date, 0)
        yield (date, value)


class Model(object):
    def __init__(self):
        if not hasattr(g, 'db'):
            raise ValueError('g has no db attribute')

class Candidate(Model):

    @classmethod
    def list(self, year, seat):
        keys = ('slug','name','total')
        stmt = """SELECT candidates.slug, candidates.name, SUM(contributions.amount) AS total
                  FROM candidates
                  JOIN contributions ON candidates.id = contributions.candidate_id
                  WHERE contributions.year = ? AND contributions.seat = ?
                  GROUP BY candidates.slug, candidates.name
                  ORDER BY total DESC"""
        return [dict(zip(keys, row)) for row in g.db.execute(stmt, (year, seat))]

    def __init__(self, slug_or_id):

        super(Candidate, self).__init__()

        cursor = g.db.cursor()

        cursor.execute("""SELECT id, name, slug FROM candidates WHERE id = ? OR slug = ?""", (slug_or_id, slug_or_id))
        db_candidate = cursor.fetchone()

        self.id = db_candidate[0]
        self.name = db_candidate[1]
        self.slug = db_candidate[2]

        cursor.close()

    def __str__(self):
        return u"%s" % self.name

    def timeline(self, start_date=None):

        end_date = datetime.date.today()
        if start_date is None:
            start_date = end_date - datetime.timedelta(days=365)

        stmt = """SELECT transaction_date, SUM(amount) AS total FROM contributions WHERE candidate_id = ? GROUP BY transaction_date ORDER BY transaction_date ASC"""
        data = dict((parse_date(row[0]), row[1]) for row in g.db.execute(stmt, (self.id,)))

        timeline = [d for d in timeline_iter(data, start_date, end_date, True)]

        return timeline

    def in_kind(self):

        headers = ('description','total','transactions')
        stmt = """SELECT description, SUM(amount) AS total, COUNT(1) AS transactions
                  FROM contributions
                  WHERE is_inkind = 1 AND candidate_id = ?
                  GROUP BY description
                  ORDER BY total DESC"""

        return [dict(zip(headers, row)) for row in g.db.execute(stmt, (self.id,))]

    def contribution_types(self):

        keys = {
            0: 'Direct',
            1: 'In-Kind',
        }

        stmt = """SELECT is_inkind, SUM(amount) AS total, COUNT(1) as transactions
                  FROM contributions
                  WHERE candidate_id = ?
                  GROUP BY is_inkind
                  ORDER BY is_inkind"""

        contrib_types = dict(zip(keys.values(), (0, 0)))

        for row in g.db.execute(stmt, (self.id,)):
            key = keys[row[0]]
            contrib_types[key] = row[1]

        return contrib_types

    def contributors(self):

        headers = ('contributor','total','transactions')
        stmt = """SELECT contributor, SUM(amount) AS total, COUNT(1) AS transactions
                  FROM contributions
                  WHERE candidate_id = ?
                  GROUP BY contributor
                  ORDER BY total DESC"""

        return [dict(zip(headers, row)) for row in g.db.execute(stmt, (self.id,)) if row[1] > 0]
