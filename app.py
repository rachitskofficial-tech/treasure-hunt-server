import os
import sqlite3
import hashlib
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, g

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')
DB_PATH = os.environ.get('DB_PATH', 'scans.db')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'change-me-now')

MESSAGES = {
    'wrong': 'Better luck next time :(',
    'clue': 'The food will be great over here, but the chef has something to tell you 👀'
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
                visitor_hash TEXT NOT NULL
            )
        ''')
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


def record_scan(route):
    db = get_db()
    db.execute(
        'INSERT INTO scans (route, scanned_at, visitor_hash) VALUES (?, ?, ?)',
        (route, datetime.now(timezone.utc).isoformat(), visitor_hash())
    )
    db.commit()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('admin_login', next=request.path))
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


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(request.args.get('next') or url_for('admin_dashboard'))
        error = 'Incorrect password.'
    return render_template('login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin')
@admin_required
def admin_dashboard():
    db = get_db()
    totals = {}
    uniques = {}
    recent = db.execute('''
        SELECT route, scanned_at FROM scans ORDER BY id DESC LIMIT 50
    ''').fetchall()
    for route in ('wrong', 'clue'):
        totals[route] = db.execute('SELECT COUNT(*) FROM scans WHERE route=?', (route,)).fetchone()[0]
        uniques[route] = db.execute('SELECT COUNT(DISTINCT visitor_hash) FROM scans WHERE route=?', (route,)).fetchone()[0]
    return render_template('dashboard.html', totals=totals, uniques=uniques, recent=recent)


@app.route('/health')
def health():
    return {'status': 'ok'}


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=False)
