import os
import sqlite3
import hashlib
import time
import secrets
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, g, jsonify
from zoneinfo import ZoneInfo

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')
DB_PATH = os.environ.get('DB_PATH', 'scans.db')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'NIK-TH-2026')
ADMIN_SESSION_TIMEOUT = int(os.environ.get('ADMIN_SESSION_TIMEOUT', '1800'))  # 30 minutes
ADMIN_AUTH_VERSION = secrets.token_hex(16)
IST = ZoneInfo('Asia/Kolkata')

MESSAGES = {
    'wrong': 'Better luck next time :(',
    'wrong2': 'Oops 😅 wrong QR...... Keep finding 🔎',
    'wrong3': 'EUREKA!!!!! 🏆🎉 Wrong QR againn... 😐',
    'clue': 'The food will be great over here, but the chef has something to tell you 👀',
    'clue2': 'Always around your neck, I check for this small plastic badge every morning to let you in. Who am I?',
    'clue3': 'I hold no hardcover, yet I change every week or month. I sit where glossy pages rest, filled with pictures and bold words.',
    'clue4': 'I hold news, events, and lost items galore, yet keep a secret behind my frame. Look past the papers pinned to my wood, and you’ll find what you seek in the very same.'
}

ROUTES = tuple(MESSAGES.keys())
CLUE_ROUTES = ('clue', 'clue2', 'clue3', 'clue4')
FAKE_ROUTES = ('wrong', 'wrong2', 'wrong3')
ROUTE_LABELS = {
    'wrong': 'Wrong QR 1',
    'wrong2': 'Wrong QR 2',
    'wrong3': 'Wrong QR 3',
    'clue': 'Clue 1',
    'clue2': 'Clue 2',
    'clue3': 'Clue 3',
    'clue4': 'Clue 4'
}


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route TEXT NOT NULL,
                scanned_at TEXT NOT NULL,
                visitor_hash TEXT NOT NULL,
                device TEXT NOT NULL DEFAULT 'Unknown',
                browser TEXT NOT NULL DEFAULT 'Unknown'
            )
        ''')
        g.db.execute('''
            CREATE TABLE IF NOT EXISTS test_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                route TEXT NOT NULL,
                scanned_at TEXT NOT NULL,
                visitor_hash TEXT NOT NULL,
                device TEXT NOT NULL DEFAULT 'Unknown',
                browser TEXT NOT NULL DEFAULT 'Unknown'
            )
        ''')
        columns = {row['name'] for row in g.db.execute('PRAGMA table_info(scans)').fetchall()}
        if 'device' not in columns:
            g.db.execute("ALTER TABLE scans ADD COLUMN device TEXT NOT NULL DEFAULT 'Unknown'")
        if 'browser' not in columns:
            g.db.execute("ALTER TABLE scans ADD COLUMN browser TEXT NOT NULL DEFAULT 'Unknown'")
        g.db.commit()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def visitor_hash():
    # Privacy-friendly approximate unique visitor counting. We do not store raw IP addresses.
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
    ua = request.headers.get('User-Agent', '')
    salt = os.environ.get('VISITOR_SALT', 'change-this-salt')
    return hashlib.sha256(f'{salt}|{ip}|{ua}'.encode()).hexdigest()[:24]


def detect_device_and_browser():
    ua = request.headers.get('User-Agent', '').lower()

    if 'iphone' in ua:
        device = 'iPhone'
    elif 'ipad' in ua:
        device = 'iPad'
    elif 'android' in ua:
        device = 'Android'
    elif 'windows' in ua:
        device = 'Windows'
    elif 'macintosh' in ua or 'mac os' in ua:
        device = 'Mac'
    elif 'linux' in ua:
        device = 'Linux'
    else:
        device = 'Unknown'

    if 'edg/' in ua or 'edge/' in ua:
        browser = 'Edge'
    elif 'opr/' in ua or 'opera' in ua:
        browser = 'Opera'
    elif 'firefox/' in ua or 'fxios/' in ua:
        browser = 'Firefox'
    elif 'crios/' in ua or ('chrome/' in ua and 'edg/' not in ua):
        browser = 'Chrome'
    elif 'safari/' in ua and 'chrome/' not in ua and 'crios/' not in ua:
        browser = 'Safari'
    else:
        browser = 'Unknown'

    return device, browser


def record_scan(route, table='scans'):
    db = get_db()
    device, browser = detect_device_and_browser()
    db.execute(
        f'''INSERT INTO {table}
           (route, scanned_at, visitor_hash, device, browser)
           VALUES (?, ?, ?, ?, ?)''',
        (route, datetime.now(timezone.utc).isoformat(), visitor_hash(), device, browser)
    )
    db.commit()


def format_ist(iso_timestamp):
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime('%d %b %Y, %I:%M:%S %p')
    except (TypeError, ValueError):
        return iso_timestamp


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        now = time.time()
        authenticated = session.get('admin') is True
        same_server_session = session.get('auth_version') == ADMIN_AUTH_VERSION
        last_activity = session.get('last_activity', 0)
        session_active = isinstance(last_activity, (int, float)) and now - last_activity < ADMIN_SESSION_TIMEOUT

        if not (authenticated and same_server_session and session_active):
            session.clear()
            return redirect(url_for('admin_login', next=request.path))

        session['last_activity'] = now
        return view(*args, **kwargs)
    return wrapped


@app.route('/', methods=['GET', 'HEAD'])
def home():
    return render_template('home.html')


def serve_route(route, test=False):
    table = 'test_scans' if test else 'scans'
    record_scan(route, table=table)
    title = f'Test {ROUTE_LABELS.get(route, route)}' if test else ROUTE_LABELS.get(route, route)
    return render_template('message.html', message=MESSAGES[route], title=title)


@app.route('/wrong')
def wrong():
    return serve_route('wrong')


@app.route('/wrong2')
def wrong2():
    return serve_route('wrong2')


@app.route('/wrong3')
def wrong3():
    return serve_route('wrong3')


@app.route('/clue')
def clue():
    return serve_route('clue')


@app.route('/clue2')
def clue2():
    return serve_route('clue2')


@app.route('/clue3')
def clue3():
    return serve_route('clue3')


@app.route('/clue4')
def clue4():
    return serve_route('clue4')


@app.route('/test/wrong')
def test_wrong():
    return serve_route('wrong', test=True)


@app.route('/test/wrong2')
def test_wrong2():
    return serve_route('wrong2', test=True)


@app.route('/test/wrong3')
def test_wrong3():
    return serve_route('wrong3', test=True)


@app.route('/test/clue')
def test_clue():
    # /test/clue is the sandbox hub. Only Section 1 records a scan after explicit selection.
    if request.args.get('section') == '1':
        return serve_route('clue', test=True)
    return render_template('test_clues.html')


@app.route('/test/clue2')
def test_clue2():
    return serve_route('clue2', test=True)


@app.route('/test/clue3')
def test_clue3():
    return serve_route('clue3', test=True)


@app.route('/test/clue4')
def test_clue4():
    return serve_route('clue4', test=True)


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session.clear()
            session['admin'] = True
            session['auth_version'] = ADMIN_AUTH_VERSION
            session['last_activity'] = time.time()
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        error = 'Incorrect password.'
    return render_template('login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


def get_dashboard_data():
    db = get_db()
    totals = {}
    uniques = {}

    for route in ROUTES:
        totals[route] = db.execute('SELECT COUNT(*) FROM scans WHERE route=?', (route,)).fetchone()[0]
        uniques[route] = db.execute('SELECT COUNT(DISTINCT visitor_hash) FROM scans WHERE route=?', (route,)).fetchone()[0]

    recent = db.execute('''
        SELECT
            route,
            visitor_hash,
            MAX(scanned_at) AS scanned_at,
            COUNT(*) AS times_recorded,
            MAX(device) AS device,
            MAX(browser) AS browser
        FROM scans
        GROUP BY route, visitor_hash
        ORDER BY MAX(id) DESC
        LIMIT 50
    ''').fetchall()

    return totals, uniques, recent


def get_test_dashboard_data():
    db = get_db()
    recent = db.execute('''
        SELECT
            route,
            visitor_hash,
            MAX(scanned_at) AS scanned_at,
            COUNT(*) AS times_recorded,
            MAX(device) AS device,
            MAX(browser) AS browser
        FROM test_scans
        GROUP BY route, visitor_hash
        ORDER BY MAX(id) DESC
        LIMIT 30
    ''').fetchall()
    total = db.execute('SELECT COUNT(*) FROM test_scans').fetchone()[0]
    return total, recent


@app.route('/admin')
@admin_required
def admin_dashboard():
    totals, uniques, recent = get_dashboard_data()
    test_total, test_recent = get_test_dashboard_data()
    recent_display = [
        {
            'route': row['route'],
            'scanned_at': format_ist(row['scanned_at']),
            'device': row['device'],
            'browser': row['browser'],
            'times_recorded': row['times_recorded']
        }
        for row in recent
    ]
    test_recent_display = [
        {
            'route': row['route'],
            'scanned_at': format_ist(row['scanned_at']),
            'device': row['device'],
            'browser': row['browser'],
            'times_recorded': row['times_recorded']
        }
        for row in test_recent
    ]
    return render_template(
        'dashboard.html',
        totals=totals,
        uniques=uniques,
        recent=recent_display,
        route_labels=ROUTE_LABELS,
        test_total=test_total,
        test_recent=test_recent_display
    )


@app.route('/admin/stats')
@admin_required
def admin_stats():
    totals, uniques, recent = get_dashboard_data()
    test_total, test_recent = get_test_dashboard_data()
    return jsonify({
        'totals': totals,
        'uniques': uniques,
        'recent': [
            {
                'route': row['route'],
                'scanned_at': format_ist(row['scanned_at']),
                'device': row['device'],
                'browser': row['browser'],
                'times_recorded': row['times_recorded']
            }
            for row in recent
        ],
        'test_total': test_total,
        'test_recent': [
            {
                'route': row['route'],
                'scanned_at': format_ist(row['scanned_at']),
                'device': row['device'],
                'browser': row['browser'],
                'times_recorded': row['times_recorded']
            }
            for row in test_recent
        ]
    })


@app.route('/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
