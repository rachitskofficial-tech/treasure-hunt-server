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
ADMIN_SESSION_TIMEOUT = int(os.environ.get('ADMIN_SESSION_TIMEOUT', '1800'))
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
KEYWORDS = {
    'clue': 'Canteen',
    'clue2': 'ID Card',
    'clue3': 'Magazine',
    'clue4': 'Notice Board',
    'wrong': 'Wrong QR',
    'wrong2': 'Keep Finding',
    'wrong3': 'Eureka? Nope'
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
            CREATE TABLE IF NOT EXISTS event_scans (
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
        g.db.execute('''
            CREATE TABLE IF NOT EXISTS system_flags (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        columns = {row['name'] for row in g.db.execute('PRAGMA table_info(scans)').fetchall()}
        if 'device' not in columns:
            g.db.execute("ALTER TABLE scans ADD COLUMN device TEXT NOT NULL DEFAULT 'Unknown'")
        if 'browser' not in columns:
            g.db.execute("ALTER TABLE scans ADD COLUMN browser TEXT NOT NULL DEFAULT 'Unknown'")
        g.db.commit()
        migrate_legacy_scans_once(g.db)
    return g.db


def migrate_legacy_scans_once(db):
    flag = db.execute("SELECT value FROM system_flags WHERE name='legacy_scans_migrated'").fetchone()
    if flag:
        return

    legacy_rows = db.execute('SELECT route, scanned_at, visitor_hash, device, browser FROM scans').fetchall()
    if legacy_rows:
        db.executemany(
            '''INSERT INTO test_scans
               (route, scanned_at, visitor_hash, device, browser)
               VALUES (?, ?, ?, ?, ?)''',
            [tuple(row) for row in legacy_rows]
        )
        db.execute('DELETE FROM scans')

    db.execute(
        "INSERT INTO system_flags(name, value) VALUES('legacy_scans_migrated', '1')"
    )
    db.commit()


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def visitor_hash():
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


def record_scan(route, table):
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


def test_dashboard_sections(routes, hub_name):
    db = get_db()
    sections = []
    for index, route in enumerate(routes, start=1):
        row = db.execute('''
            SELECT COUNT(*) AS total, MAX(scanned_at) AS last_scan
            FROM test_scans WHERE route=?
        ''', (route,)).fetchone()
        latest = db.execute('''
            SELECT device, browser FROM test_scans
            WHERE route=? ORDER BY id DESC LIMIT 1
        ''', (route,)).fetchone()
        sections.append({
            'number': index,
            'route': route,
            'label': ROUTE_LABELS[route],
            'keyword': KEYWORDS[route],
            'total': row['total'],
            'last_scan': format_ist(row['last_scan']) if row['last_scan'] else 'No test runs yet',
            'device': latest['device'] if latest else 'None',
            'browser': latest['browser'] if latest else 'None',
            'hub': hub_name
        })
    return sections


def test_section(route, hub):
    if route not in ROUTES:
        return redirect(url_for(hub))
    record_scan(route, 'test_scans')
    return render_template('message.html', message=MESSAGES[route], title=f'Test {ROUTE_LABELS[route]}')


def event_section(route):
    if route not in ROUTES:
        return redirect(url_for('home'))
    record_scan(route, 'event_scans')
    return render_template('message.html', message=MESSAGES[route], title=ROUTE_LABELS[route])


# TEST DASHBOARD: /wrong
@app.route('/wrong')
def wrong_test_dashboard():
    return render_template('test_wrong.html', sections=test_dashboard_sections(FAKE_ROUTES, 'wrong_test_dashboard'))


@app.route('/wrong/section/<route>')
def wrong_test_section(route):
    return test_section(route, 'wrong_test_dashboard')


# TEST DASHBOARD: /clue
@app.route('/clue')
def clue_test_dashboard():
    return render_template('test_clues.html', sections=test_dashboard_sections(CLUE_ROUTES, 'clue_test_dashboard'))


@app.route('/clue/section/<route>')
def clue_test_section(route):
    return test_section(route, 'clue_test_dashboard')


# Backward-compatible test aliases
@app.route('/test/wrong')
def test_wrong_alias():
    return redirect(url_for('wrong_test_dashboard'))


@app.route('/test/wrong/<route>')
def test_wrong_section_alias(route):
    return redirect(url_for('wrong_test_section', route=route))


@app.route('/test/wrong2')
def test_wrong2_alias():
    return redirect(url_for('wrong_test_section', route='wrong2'))


@app.route('/test/wrong3')
def test_wrong3_alias():
    return redirect(url_for('wrong_test_section', route='wrong3'))


@app.route('/test/clue')
def test_clue_alias():
    return redirect(url_for('clue_test_dashboard'))


@app.route('/test/clue/<route>')
def test_clue_section_alias(route):
    return redirect(url_for('clue_test_section', route=route))


@app.route('/test/clue2')
def test_clue2_alias():
    return redirect(url_for('clue_test_section', route='clue2'))


@app.route('/test/clue3')
def test_clue3_alias():
    return redirect(url_for('clue_test_section', route='clue3'))


@app.route('/test/clue4')
def test_clue4_alias():
    return redirect(url_for('clue_test_section', route='clue4'))


# LIVE EVENT QR routes. These are the URLs to encode into the real QR codes.
@app.route('/event/wrong')
def event_wrong():
    return event_section('wrong')


@app.route('/event/wrong2')
def event_wrong2():
    return event_section('wrong2')


@app.route('/event/wrong3')
def event_wrong3():
    return event_section('wrong3')


@app.route('/event/clue')
def event_clue():
    return event_section('clue')


@app.route('/event/clue2')
def event_clue2():
    return event_section('clue2')


@app.route('/event/clue3')
def event_clue3():
    return event_section('clue3')


@app.route('/event/clue4')
def event_clue4():
    return event_section('clue4')


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
        totals[route] = db.execute('SELECT COUNT(*) FROM event_scans WHERE route=?', (route,)).fetchone()[0]
        uniques[route] = db.execute('SELECT COUNT(DISTINCT visitor_hash) FROM event_scans WHERE route=?', (route,)).fetchone()[0]
    recent = db.execute('''
        SELECT route, visitor_hash, MAX(scanned_at) AS scanned_at,
               COUNT(*) AS times_recorded, MAX(device) AS device, MAX(browser) AS browser
        FROM event_scans
        GROUP BY route, visitor_hash
        ORDER BY MAX(id) DESC
        LIMIT 50
    ''').fetchall()
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
            'browser': row['browser'],
            'times_recorded': row['times_recorded']
        }
        for row in recent
    ]
    return render_template('dashboard.html', totals=totals, uniques=uniques, recent=recent_display, route_labels=ROUTE_LABELS)


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
                'browser': row['browser'],
                'times_recorded': row['times_recorded']
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
