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
    'clue': 'The food will be great over here, but the chef has something to tell you 👀',
    'clue2': 'Always around your neck, I check for this small plastic badge every morning to let you in. Who am I?',
    'clue3': 'I hold no hardcover, yet I change every week or month. I sit where glossy pages rest, filled with pictures and bold words.',
    'clue4': 'I hold news, events, and lost items galore, yet keep a secret behind my frame. Look past the papers pinned to my wood, and you’ll find what you seek in the very same.'
}

ROUTES = tuple(MESSAGES.keys())
ROUTE_LABELS = {
    'wrong': 'Wrong QR',
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


def record_scan(route):
    db = get_db()
    device, browser = detect_device_and_browser()
    db.execute(
        '''INSERT INTO scans
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


@app.route('/wrong')
def wrong():
    record_scan('wrong')
    return render_template('message.html', message=MESSAGES['wrong'], title='Try Again')


@app.route('/clue')
def clue():
    record_scan('clue')
    return render_template('message.html', message=MESSAGES['clue'], title='You Found a Clue')


@app.route('/clue2')
def clue2():
    record_scan('clue2')
    return render_template('message.html', message=MESSAGES['clue2'], title='Clue 2')


@app.route('/clue3')
def clue3():
    record_scan('clue3')
    return render_template('message.html', message=MESSAGES['clue3'], title='Clue 3')


@app.route('/clue4')
def clue4():
    record_scan('clue4')
    return render_template('message.html', message=MESSAGES['clue4'], title='Clue 4')


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
    recent = db.execute('''
        SELECT route, scanned_at, device, browser
        FROM scans ORDER BY id DESC LIMIT 50
    ''').fetchall()
    for route in ROUTES:
        totals[route] = db.execute('SELECT COUNT(*) FROM scans WHERE route=?', (route,)).fetchone()[0]
        uniques[route] = db.execute('SELECT COUNT(DISTINCT visitor_hash) FROM scans WHERE route=?', (route,)).fetchone()[0]
    return totals, uniques, recent


@app.route('/admin')
@admin_required
def admin_dashboard():
    totals, uniques, recent = get_dashboard_data()
    recent_display = [
        {
            'route': row['route'],
            'scanned_at': format_ist(row['scanned_at']),
            'device': row['device'],
            'browser': row['browser']
        }
        for row in recent
    ]
    return render_template(
        'dashboard.html',
        totals=totals,
        uniques=uniques,
        recent=recent_display,
        route_labels=ROUTE_LABELS
    )


@app.route('/admin/stats')
@admin_required
def admin_stats():
    totals, uniques, recent = get_dashboard_data()
    return jsonify({
        'totals': totals,
        'uniques': uniques,
        'recent': [
            {
                'route': row['route'],
                'scanned_at': format_ist(row['scanned_at']),
                'device': row['device'],
                'browser': row['browser']
            }
            for row in recent
        ]
    })


@app.route('/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
