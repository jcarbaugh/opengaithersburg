import datetime
import json
import os
import requests
import sqlite3

from saucebrush import emitters, sources, filters, run_recipe, Recipe

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'og.db')

STATE_ABBRS = {
    'AK': 'Alaska', 'AL': 'Alabama', 'AR': 'Arkansas', 'AS': 'American Samoa',
    'AZ': 'Arizona', 'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut',
    'DC': 'District of Columbia', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'GU': 'Guam', 'HI': 'Hawaii', 'IA': 'Iowa', 'ID': 'Idaho', 'IL': 'Illinois',
    'IN': 'Indiana', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
    'MA': 'Massachusetts', 'MD': 'Maryland', 'ME': 'Maine', 'MI': 'Michigan',
    'MN': 'Minnesota', 'MO': 'Missouri', 'MP': 'Northern Mariana Islands',
    'MS': 'Mississippi', 'MT': 'Montana', 'NC': 'North Carolina', 'ND': 'North Dakota',
    'NE': 'Nebraska', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico',
    'NV': 'Nevada', 'NY': 'New York', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon',
    'PA': 'Pennsylvania', 'PR': 'Puerto Rico', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VA': 'Virginia',
    'VI': 'Virgin Islands', 'VT': 'Vermont', 'WA': 'Washington', 'WI': 'Wisconsin',
    'WV': 'West Virginia', 'WY': 'Wyoming'
}
STATE_NAMES = dict((v, k) for k, v in STATE_ABBRS.iteritems())

CANDIDATES = {
    'cathy-drzyzgula': {'id': 37, 'name': 'Cathy Drzyzgula'},
    'jud-ashman': {'id': 36, 'name': 'Jud Ashman'},
    'paula-ross': {'id': 38, 'name': 'Paula Ross'},
    'ryan-spiegel': {'id': 34, 'name': 'Ryan Spiegel'},
    'thomas-s-rowse': {'id': 35, 'name': 'Thomas S. Rowse'},
}

AMOUNT_FIELDS = ('cash_amount','check_amount','credit_amount','inkind_amount')

class GeocoderFilter(filters.Filter):

    ENDPOINT = "http://where.yahooapis.com/geocode"

    def __init__(self, app_id):
        super(GeocoderFilter, self).__init__()
        self.app_id = app_id

    def geocode(self, address):

        params = {
            'q': address,
            'appid': self.app_id,
            'flags': 'CJ',
        }

        resp = requests.get(self.ENDPOINT, params=params)
        data = json.loads(resp.content)

        try:

            result = data['ResultSet']['Results'][0]
            return (result['latitude'], result['longitude'])

        except KeyError:
            pass
        except IndexError:
            pass

        return (None, None)

    def process_record(self, record):

        addr = " ".join(record[k] for k in ('address', 'city', 'state', 'zipcode'))

        ll = self.geocode(addr)

        record['latitude'] = ll[0]
        record['longitude'] = ll[1]

        return record

class InvalidRecordFilter(filters.ConditionalFilter):

    def test_record(self, record):
        return None not in record.keys()

class InKindFilter(filters.Filter):

    def process_record(self, record):
        record['description'] = record['inkind_type'].strip() or None
        record['is_inkind'] = record['description'] is not None
        del record['inkind_type']
        return record

class CandidateFilter(filters.Filter):

    def __init__(self):
        self._candidates = {}
        for slug, candidate in CANDIDATES.iteritems():
            self._candidates[candidate['name']] = candidate['id']

    def process_record(self, record):
        record['candidate_id'] = self._candidates.get(record['candidate'], None)
        return record

def parse_datetime(dt):
    return datetime.datetime.strptime(dt, '%m/%d/%Y %I:%M:%S %p').date()

def clean_state(state):
    state = state.strip()
    if state in STATE_NAMES:
        state = STATE_NAMES[state]
    elif state not in STATE_ABBRS:
        state = None
    return state

def merge_amounts(*amounts):
    return sum(amounts)

#
# recipes
#

def _err_stream(datatype):

    def timestamp():
        return datetime.datetime.utcnow().isoformat()

    log_path = os.path.join(PROJECT_ROOT, 'logs')

    if not os.path.exists(log_path):
        os.mkdir(log_path)

    path = os.path.join(log_path, 'err-%s.csv' % datatype)
    fieldnames = ('exception', 'record', 'timestamp')

    return Recipe(
        filters.FieldModifier('record', lambda d: json.dumps(d)),
        filters.FieldAdder('timestamp', timestamp),
        emitters.CSVEmitter(open(path, 'w'), fieldnames=fieldnames),
    )


def create_tables():

    if os.path.exists(DB_PATH):
        os.unlink(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """ CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                slug TEXT
            )""")

    cur.execute("""DELETE FROM candidates""")

    for slug, candidate in CANDIDATES.iteritems():
        stmt = """INSERT INTO candidates (id, name, slug) VALUES (?, ?, ?)"""
        cur.execute(stmt, (candidate['id'], candidate['name'], slug))

    cur.execute(
        """ CREATE TABLE IF NOT EXISTS contributions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER,
                seat TEXT,
                candidate TEXT,
                candidate_id INTEGER,
                contributor TEXT,
                address TEXT,
                city TEXT,
                state TEXT,
                zipcode TEXT,
                latitude REAL,
                longitude REAL,
                amount REAL,
                description TEXT,
                is_inkind INTEGER,
                to_date REAL,
                transaction_date TEXT,
                status TEXT
            )""")

    cur.execute("""DELETE FROM contributions""")

    cur.close()
    conn.close()

def load_contributions():

    csv_path = os.path.join(PROJECT_ROOT, 'data', 'Contributions.csv')

    run_recipe(
        sources.CSVSource(open(csv_path)),
        InvalidRecordFilter(),
        filters.FieldRenamer({
            'candidate': 'Campaign Name',
            'contributor': 'Contributor Name',
            'address': 'Address',
            'city': 'City',
            'state': 'State',
            'zipcode': 'Zip',
            'cash_amount': 'Cash Amount',
            'check_amount': 'Check Amount',
            'credit_amount': 'Credit Amount',
            'inkind_amount': 'In-Kind Donation Value',
            'inkind_type': 'In-Kind Donation Type',
            'to_date': 'Aggregate To Date',
            'transaction_date': 'Transaction Date',
            'status': 'Status',
        }),
        filters.FieldAdder('year', 2011),
        filters.FieldAdder('seat', 'council'),
        filters.FieldAdder('latitude', None),
        filters.FieldAdder('longitude', None),
        GeocoderFilter('Kv3.btLV34EuebZGMzi1KaqI_BOPhPjx7FtbvED.umr8DGUq0NysoGN0XIIIDRU-'),
        CandidateFilter(),
        filters.FieldModifier('to_date', float),
        filters.FieldModifier(AMOUNT_FIELDS, float),
        filters.FieldMerger({'amount': AMOUNT_FIELDS}, merge_amounts),
        filters.FieldModifier('state', clean_state),
        filters.FieldModifier('transaction_date', parse_datetime),
        InKindFilter(),
        emitters.SqliteEmitter(DB_PATH, 'contributions'),
        #emitters.DebugEmitter(),
        error_stream = _err_stream('contributions'),
    )

if __name__ == '__main__':

    create_tables()
    load_contributions()

"""



INSERT INTO candidates (name, year, seat)
SELECT DISTINCT candidate, '2011', 'council'
FROM contributions;

UPDATE contributions
JOIN candidates ON candidates.name = contributions.candidate
SET contributions.candidate_id = candidates.id;

SELECT candidate_id, SUM(amount) AS total, COUNT(1) AS transactions
FROM contributions
GROUP BY candidate_id
ORDER BY total DESC;

SELECT candidate_id, is_inkind, SUM(amount) AS total, COUNT(1) as transactions
FROM contributions
GROUP BY candidate_id, is_inkind
ORDER BY candidate_id, is_inkind;

SELECT contributor, candidate_id, SUM(amount) AS total, COUNT(1) AS transactions
FROM contributions
GROUP BY contributor, candidate_id
ORDER BY total DESC;

SELECT description, SUM(amount) AS total, COUNT(1) AS transactions
FROM contributions
WHERE is_inkind = 1
GROUP BY description;

SELECT candidate_id, description, SUM(amount) AS total, COUNT(1) AS transactions
FROM contributions
WHERE is_inkind = 1
GROUP BY candidate_id, description;

SELECT transaction_date, SUM(amount) AS total, COUNT(1) AS transactions
FROM contributions
WHERE candidate_id = 8
GROUP BY transaction_date
ORDER BY transaction_date ASC;

"""

