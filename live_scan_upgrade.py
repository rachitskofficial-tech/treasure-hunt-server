from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import jsonify, request

import app as app_module


def _ensure_column(db, table, column, definition):
    columns = {row['name'] for row in db.execute(f'PRAGMA table_info({table})').fetchall()}
    if column not in columns:
        db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def ensure_schema():
    db = app_module.get_db()
    _ensure_column(db, 'teams', 'temp_id', 'TEXT')
    _ensure_column(db, 'live_scans', 'temp_id', 'TEXT')
    _ensure_column(db, 'live_scans', 'target_url', 'TEXT')
    _ensure_column(db, 'live_scans', 'device', "TEXT NOT NULL DEFAULT 'Unknown'")
    _ensure_column(db, 'live_scans', 'browser', "TEXT NOT NULL DEFAULT 'Unknown'")
    db.commit()
    return db


def enhanced_record_live_scan(route, team, target_url=None):
    db = ensure_schema()
    temp_id = team['temp_id'] if 'temp_id' in team.keys() else None
    if not target_url:
        target_url = request.url
    device, browser = app_module.detect_device_and_browser()
    db.execute('''
        INSERT INTO live_scans
        (team_id, team_number, route, scanned_at, temp_id, target_url, device, browser)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        team['id'], team['team_number'], route,
        datetime.now(timezone.utc).isoformat(), temp_id,
        target_url, device, browser
    ))
    db.commit()


# Existing /event/* handlers call app_module.record_live_scan by global lookup,
# so replacing this function upgrades all existing event routes without creating duplicates.
app_module.record_live_scan = enhanced_record_live_scan


def _resolve_route(raw_value):
    parsed = urlparse(raw_value)
    path = parsed.path.rstrip('/')
    if path.startswith('/event/'):
        route = path.split('/event/', 1)[1].split('/', 1)[0]
        if route in app_module.ROUTES:
            return route
    # Also accept a same-origin relative event URL.
    if path.startswith('/event/'):
        return path.rsplit('/', 1)[-1]
    return None


@app_module.app.post('/api/scan')
def api_scan():
    """Record a scan from the working camera page, then let the client navigate to the QR target."""
    team = app_module.get_team_from_cookie()
    if not team:
        return jsonify({'ok': False, 'error': 'TEAM_NOT_REGISTERED'}), 403

    payload = request.get_json(silent=True) or {}
    raw_value = str(payload.get('url') or payload.get('rawValue') or '').strip()
    if not raw_value:
        return jsonify({'ok': False, 'error': 'EMPTY_QR'}), 400

    parsed = urlparse(raw_value)
    if parsed.scheme not in ('http', 'https'):
        return jsonify({'ok': False, 'error': 'UNSUPPORTED_QR_TARGET'}), 400

    route = _resolve_route(raw_value)
    if route is None:
        # The event scanner is still allowed to navigate to a normal HTTPS URL,
        # but it is recorded under EXTERNAL so the dashboard never loses the scan.
        route = 'external'

    enhanced_record_live_scan(route, team, raw_value)
    return jsonify({
        'ok': True,
        'team_number': team['team_number'],
        'temp_id': team['temp_id'] if 'temp_id' in team.keys() else None,
        'route': route,
        'target_url': raw_value
    })


def enhanced_dashboard_data():
    db = ensure_schema()
    totals = {
        route: db.execute('SELECT COUNT(*) FROM live_scans WHERE route=?', (route,)).fetchone()[0]
        for route in app_module.ROUTES
    }
    teams = []
    for number in app_module.TEAM_SLOTS:
        row = db.execute('''
            SELECT id, team_number, name, uucms_number, contact_number, temp_id
            FROM teams WHERE team_number=? AND active=1
        ''', (number,)).fetchone()
        scan_count = db.execute(
            'SELECT COUNT(*) FROM live_scans WHERE team_number=?', (number,)
        ).fetchone()[0]
        teams.append({
            'team_number': number,
            'registered': bool(row),
            'name': row['name'] if row else '',
            'uucms': '',
            'contact': row['contact_number'] if row else '',
            'temp_id': row['temp_id'] if row and row['temp_id'] else 'Legacy registration',
            'scan_count': scan_count
        })

    recent = db.execute('''
        SELECT team_number, temp_id, route, scanned_at, target_url
        FROM live_scans
        ORDER BY id DESC
        LIMIT 30
    ''').fetchall()
    return totals, teams, recent


app_module.get_live_dashboard_data = enhanced_dashboard_data


# Ensure the migration happens at startup too, so the first dashboard request is clean.
with app_module.app.app_context():
    ensure_schema()
