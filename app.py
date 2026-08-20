import os
import sqlite3
import hashlib
import time
import secrets
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, session, g, jsonify, make_response

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')
DB_PATH = os.environ.get('DB_PATH', 'scans.db')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'NIK-TH-2026')
ADMIN_SESSION_TIMEOUT = int(os.environ.get('ADMIN_SESSION_TIMEOUT', '1800'))
ADMIN_AUTH_VERSION = secrets.token_hex(16)
IST = timezone(timedelta(hours=5, minutes=30), name='IST')
TEAM_COOKIE = 'nikshepa_team_token'
TEAM_SLOTS = tuple(range(1, 7))
TEMP_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
DENIED_MESSAGE = "Sorry, we couldn't process with the event. Contact team NIKSHEPA"

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
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_number INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                uucms_number TEXT NOT NULL,
                contact_number TEXT NOT NULL,
                temp_id_hash TEXT NOT NULL UNIQUE,
                device_token_hash TEXT NOT NULL UNIQUE,
                registered_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
        ''')
        g.db.execute('''
            CREATE TABLE IF NOT EXISTS live_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                team_number INTEGER NOT NULL,
                route TEXT NOT NULL,
                scanned_at TEXT NOT NULL
            )
        ''')
        g.db.commit()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def hash_value(value):
    salt = os.environ.get('VISITOR_SALT', 'change-this-salt')
    return hashlib.sha256(f'{salt}|{value}'.encode()).hexdigest()


def visitor_hash():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()
    ua = request.headers.get('User-Agent', '')
    return hash_value(f'{ip}|{ua}')[:24]


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


def new_temp_id(team_number):
    suffix = ''.join(secrets.choice(TEMP_ALPHABET) for _ in range(6))
    return f'NIK-{team_number:02d}-{suffix}'


def get_team_from_cookie():
    raw = request.cookies.get(TEAM_COOKIE)
    if not raw:
        return None
    token_hash = hash_value(raw)
    return get_db().execute('''
        SELECT * FROM teams
        WHERE device_token_hash=? AND active=1
    ''', (token_hash,)).fetchone()


def team_gate_response():
    return render_template('message.html', title='Event Access Restricted', message=DENIED_MESSAGE)


def record_live_scan(route, team):
    db = get_db()
    db.execute('''
        INSERT INTO live_scans (team_id, team_number, route, scanned_at)
        VALUES (?, ?, ?, ?)
    ''', (team['id'], team['team_number'], route, datetime.now(timezone.utc).isoformat()))
    db.commit()


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
            return redirect('/admin/login?next=' + request.path)
        session['last_activity'] = now
        return view(*args, **kwargs)
    return wrapped


def format_ist(iso_timestamp):
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST).strftime('%d %b %Y, %I:%M:%S %p')
    except (TypeError, ValueError):
        return iso_timestamp or ''


def get_test_sections(routes):
    db = get_db()
    sections = []
    for index, route in enumerate(routes, start=1):
        row = db.execute('SELECT COUNT(*) AS total FROM test_scans WHERE route=?', (route,)).fetchone()
        sections.append({
            'number': index,
            'route': route,
            'label': ROUTE_LABELS[route],
            'keyword': KEYWORDS[route],
            'total': row['total']
        })
    return sections


def render_test_scan(route):
    db = get_db()
    device, browser = detect_device_and_browser()
    db.execute('''
        INSERT INTO test_scans (route, scanned_at, visitor_hash, device, browser)
        VALUES (?, ?, ?, ?, ?)
    ''', (route, datetime.now(timezone.utc).isoformat(), visitor_hash(), device, browser))
    db.commit()
    return render_template('message.html', title=f'Test {ROUTE_LABELS[route]}', message=MESSAGES[route])


@app.route('/register', methods=['GET', 'POST'])
def register_team():
    db = get_db()
    error = None
    success = False
    temp_id = None
    registered_team_number = None

    current_team = get_team_from_cookie()
    if current_team:
        return render_template('register.html', success=True, temp_id='ALREADY REGISTERED', team_number=current_team['team_number'], available_teams=[])

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        uucms = request.form.get('uucms', '').strip()
        contact = request.form.get('contact', '').strip()
        team_raw = request.form.get('team_number', '').strip()

        try:
            team_number = int(team_raw)
        except ValueError:
            team_number = 0

        if not name or not uucms or not contact or team_number not in TEAM_SLOTS:
            error = 'Please complete all four fields and choose a valid team number.'
        else:
            existing_team = db.execute('SELECT id FROM teams WHERE team_number=? AND active=1', (team_number,)).fetchone()
            if existing_team:
                error = f'Team {team_number} is already registered. Please choose another team.'
            else:
                raw_device_token = secrets.token_hex(32)
                device_token_hash = hash_value(raw_device_token)
                temp_id = new_temp_id(team_number)
                temp_hash = hash_value(temp_id)
                try:
                    db.execute('''
                        INSERT INTO teams
                        (team_number, name, uucms_number, contact_number, temp_id_hash, device_token_hash, registered_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        team_number, name, uucms, contact, temp_hash,
                        device_token_hash, datetime.now(timezone.utc).isoformat()
                    ))
                    db.commit()
                    response = make_response(render_template(
                        'register.html',
                        success=True,
                        temp_id=temp_id,
                        team_number=team_number,
                        available_teams=[]
                    ))
                    response.set_cookie(
                        TEAM_COOKIE,
                        raw_device_token,
                        max_age=48 * 60 * 60,
                        httponly=True,
                        samesite='Lax',
                        secure=request.is_secure
                    )
                    return response
                except sqlite3.IntegrityError:
                    db.rollback()
                    error = 'That team could not be registered. Please try another team.'

    available = [n for n in TEAM_SLOTS if not db.execute('SELECT 1 FROM teams WHERE team_number=? AND active=1', (n,)).fetchone()]
    return render_template('register.html', success=success, temp_id=temp_id, team_number=registered_team_number, available_teams=available, error=error)


@app.route('/team')
def team_status():
    team = get_team_from_cookie()
    if not team:
        return team_gate_response()
    return render_template('message.html', title=f'Team {team["team_number"]}', message=f'Team {team["team_number"]} is registered and this phone is authorised for the event.')


# Test dashboards remain separate from live event access.
@app.route('/wrong')
def wrong_test_dashboard():
    return render_template('test_wrong.html', sections=get_test_sections(FAKE_ROUTES))


@app.route('/clue')
def clue_test_dashboard():
    return render_template('test_clues.html', sections=get_test_sections(CLUE_ROUTES))


@app.route('/wrong/<route>')
def wrong_test_section(route):
    if route not in FAKE_ROUTES:
        return redirect('/wrong')
    return render_test_scan(route)


@app.route('/clue/<route>')
def clue_test_section(route):
    if route not in CLUE_ROUTES:
        return redirect('/clue')
    return render_test_scan(route)


@app.route('/test/wrong')
def test_wrong():
    return redirect('/wrong')


@app.route('/test/wrong2')
def test_wrong2():
    return render_test_scan('wrong2')


@app.route('/test/wrong3')
def test_wrong3():
    return render_test_scan('wrong3')


@app.route('/test/wrong/<route>')
def test_wrong_section(route):
    return redirect('/wrong/' + route)


@app.route('/test/clue')
def test_clue():
    return redirect('/clue')


@app.route('/test/clue2')
def test_clue2():
    return render_test_scan('clue2')


@app.route('/test/clue3')
def test_clue3():
    return render_test_scan('clue3')


@app.route('/test/clue4')
def test_clue4():
    return render_test_scan('clue4')


@app.route('/test/clue/<route>')
def test_clue_section(route):
    return redirect('/clue/' + route)


# Live event QR routes. A registered team phone is required.
def live_event_scan(route):
    team = get_team_from_cookie()
    if not team:
        return team_gate_response()
    record_live_scan(route, team)
    return render_template('message.html', title=ROUTE_LABELS[route], message=MESSAGES[route])


@app.route('/event/wrong')
def event_wrong():
    return live_event_scan('wrong')


@app.route('/event/wrong2')
def event_wrong2():
    return live_event_scan('wrong2')


@app.route('/event/wrong3')
def event_wrong3():
    return live_event_scan('wrong3')


@app.route('/event/clue')
def event_clue():
    return live_event_scan('clue')


@app.route('/event/clue2')
def event_clue2():
    return live_event_scan('clue2')


@app.route('/event/clue3')
def event_clue3():
    return live_event_scan('clue3')


@app.route('/event/clue4')
def event_clue4():
    return live_event_scan('clue4')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session.clear()
            session['admin'] = True
            session['auth_version'] = ADMIN_AUTH_VERSION
            session['last_activity'] = time.time()
            return redirect('/admin')
        error = 'Incorrect password.'
    return render_template('login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect('/admin/login')


@app.route('/admin/teams/edit/<int:team_number>', methods=['GET', 'POST'])
@admin_required
def admin_team_edit(team_number):
    db = get_db()
    team = db.execute('SELECT * FROM teams WHERE team_number=? AND active=1', (team_number,)).fetchone()
    if not team:
        return redirect('/admin')
    error = None
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        uucms = request.form.get('uucms', '').strip()
        contact = request.form.get('contact', '').strip()
        if not name or not uucms or not contact:
            error = 'Name, UUCMS Number, and Contact Number are required.'
        else:
            db.execute('UPDATE teams SET name=?, uucms_number=?, contact_number=? WHERE team_number=?', (name, uucms, contact, team_number))
            db.commit()
            return redirect('/admin')
        team = db.execute('SELECT * FROM teams WHERE team_number=? AND active=1', (team_number,)).fetchone()
    return render_template('team_edit.html', team=team, error=error)


@app.route('/admin/teams/clear/<int:team_number>', methods=['POST'])
@admin_required
def admin_team_clear(team_number):
    db = get_db()
    team = db.execute('SELECT id FROM teams WHERE team_number=? AND active=1', (team_number,)).fetchone()
    if team:
        db.execute('DELETE FROM live_scans WHERE team_id=?', (team['id'],))
        db.commit()
    return redirect('/admin')


@app.route('/admin/teams/remove/<int:team_number>', methods=['POST'])
@admin_required
def admin_team_remove(team_number):
    db = get_db()
    team = db.execute('SELECT id FROM teams WHERE team_number=? AND active=1', (team_number,)).fetchone()
    if team:
        db.execute('DELETE FROM live_scans WHERE team_id=?', (team['id'],))
        db.execute('DELETE FROM teams WHERE id=?', (team['id'],))
        db.commit()
    return redirect('/admin')


def get_live_dashboard_data():
    db = get_db()
    totals = {route: db.execute('SELECT COUNT(*) FROM live_scans WHERE route=?', (route,)).fetchone()[0] for route in ROUTES}
    teams = []
    for number in TEAM_SLOTS:
        row = db.execute('''
            SELECT id, team_number, name, uucms_number, contact_number
            FROM teams WHERE team_number=? AND active=1
        ''', (number,)).fetchone()
        scan_count = db.execute('SELECT COUNT(*) FROM live_scans WHERE team_number=?', (number,)).fetchone()[0]
        teams.append({
            'team_number': number,
            'registered': bool(row),
            'name': row['name'] if row else '',
            'uucms': row['uucms_number'] if row else '',
            'contact': row['contact_number'] if row else '',
            'scan_count': scan_count
        })
    recent = db.execute('''
        SELECT team_number, route
        FROM live_scans
        ORDER BY id DESC
        LIMIT 30
    ''').fetchall()
    return totals, teams, recent


@app.route('/admin')
@admin_required
def admin_dashboard():
    totals, teams, recent = get_live_dashboard_data()
    return render_template(
        'dashboard.html',
        totals=totals,
        teams=teams,
        recent=[{'team_number': row['team_number'], 'route': row['route']} for row in recent],
        route_labels=ROUTE_LABELS
    )


@app.route('/admin/stats')
@admin_required
def admin_stats():
    totals, teams, recent = get_live_dashboard_data()
    return jsonify({
        'totals': totals,
        'teams': teams,
        'recent': [{'team_number': row['team_number'], 'route': row['route']} for row in recent]
    })


@app.route('/', methods=['GET', 'HEAD'])
def home():
    return render_template('home.html')


@app.route('/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
