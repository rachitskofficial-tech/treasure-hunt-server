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
    device, browser = app_module.detect_device_and_browser()
    db.execute('''
        INSERT INTO live_scans
        (team_id, team_number, route, scanned_at, temp_id, target_url, device, browser)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        team['id'], team['team_number'], route,
        datetime.now(timezone.utc).isoformat(), temp_id,
        target_url or request.url, device, browser
    ))
    db.commit()


app_module.record_live_scan = enhanced_record_live_scan


def _resolve_route(raw_value):
    """Resolve the route key from the actual QR payload, regardless of URL style."""
    text = str(raw_value or '').strip()
    parsed = urlparse(text)
    path = parsed.path.rstrip('/')

    if text in app_module.ROUTES:
        return text

    segments = [segment for segment in path.split('/') if segment]
    for segment in reversed(segments):
        if segment in app_module.ROUTES:
            return segment

    return None


@app_module.app.post('/api/scan')
def api_scan():
    """Record the scan first. The browser then navigates to the QR destination."""
    team = app_module.get_team_from_cookie()
    if not team:
        return jsonify({'ok': False, 'error': 'TEAM_NOT_REGISTERED'}), 403

    payload = request.get_json(silent=True) or {}
    raw_value = str(payload.get('url') or payload.get('rawValue') or '').strip()
    if not raw_value:
        return jsonify({'ok': False, 'error': 'EMPTY_QR'}), 400

    parsed = urlparse(raw_value)
    route = _resolve_route(raw_value)
    if route is None and parsed.scheme not in ('http', 'https'):
        return jsonify({'ok': False, 'error': 'UNSUPPORTED_QR_TARGET'}), 400

    target_url = raw_value
    if route and parsed.scheme not in ('http', 'https'):
        target_url = request.host_url.rstrip('/') + '/event/' + route
    elif route and parsed.scheme in ('http', 'https') and parsed.netloc == request.host:
        target_url = raw_value

    enhanced_record_live_scan(route or 'external', team, target_url)
    return jsonify({
        'ok': True,
        'team_number': team['team_number'],
        'temp_id': team['temp_id'] if 'temp_id' in team.keys() else None,
        'route': route or 'external',
        'target_url': target_url
    })


def fake_qr_stats(db):
    """Return unique teams for each fake QR in first-scan order.

    A team is counted once per fake QR. If it scans the same fake QR repeatedly,
    only its earliest live_scans row is retained for the leaderboard. The lower
    database id is the authoritative first-come-first-served order.
    """
    stats = {}
    for route in app_module.FAKE_ROUTES:
        rows = db.execute('''
            SELECT team_number, temp_id, MIN(id) AS first_scan_id, MIN(scanned_at) AS first_scanned_at
            FROM live_scans
            WHERE route=?
            GROUP BY team_id, team_number, temp_id
            ORDER BY first_scan_id ASC
        ''', (route,)).fetchall()
        teams = [{
            'team_number': row['team_number'],
            'temp_id': row['temp_id'] or 'Legacy registration',
            'first_scan_id': row['first_scan_id'],
            'scanned_at': row['first_scanned_at']
        } for row in rows]
        stats[route] = {
            'label': app_module.ROUTE_LABELS.get(route, route),
            'keyword': app_module.KEYWORDS.get(route, route),
            'count': len(teams),
            'teams': teams
        }
    return stats


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
        scan_count = db.execute('SELECT COUNT(*) FROM live_scans WHERE team_number=?', (number,)).fetchone()[0]
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


def enhanced_admin_stats():
    totals, teams, recent = enhanced_dashboard_data()
    db = ensure_schema()
    fake_stats = fake_qr_stats(db)
    return jsonify({
        'totals': totals,
        'teams': teams,
        'fake_stats': fake_stats,
        'recent': [{
            'team_number': row['team_number'],
            'temp_id': row['temp_id'] or 'Legacy registration',
            'route': row['route'],
            'scanned_at': row['scanned_at'],
            'target_url': row['target_url'] or ''
        } for row in recent]
    })


app_module.app.view_functions['admin_stats'] = app_module.admin_required(enhanced_admin_stats)

with app_module.app.app_context():
    ensure_schema()
