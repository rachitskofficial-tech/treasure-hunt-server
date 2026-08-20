import sqlite3
from datetime import datetime, timezone
from flask import jsonify, render_template, request, session

from app import (
    app,
    CLUE_ROUTES,
    DENIED_MESSAGE,
    FAKE_ROUTES,
    KEYWORDS,
    MESSAGES,
    ROUTE_LABELS,
    get_db,
    get_team_from_cookie,
    record_live_scan,
)

TOTAL_CHECKPOINTS = 7
CHECKPOINT_MAP = {'clue': 1, 'clue2': 2, 'clue3': 3, 'clue4': 4}
ALL_EVENT_ROUTES = set(CLUE_ROUTES) | set(FAKE_ROUTES)


def ensure_participant_tables():
    db = get_db()
    db.execute('''
        CREATE TABLE IF NOT EXISTS checkpoint_clears (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_id INTEGER NOT NULL,
            team_number INTEGER NOT NULL,
            checkpoint_number INTEGER NOT NULL,
            route TEXT NOT NULL,
            cleared_at TEXT NOT NULL,
            UNIQUE(team_id, checkpoint_number)
        )
    ''')
    db.execute('''
        CREATE TABLE IF NOT EXISTS team_finishes (
            team_id INTEGER PRIMARY KEY,
            team_number INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            elapsed_seconds REAL NOT NULL
        )
    ''')
    db.commit()
    return db


def admin_session_active():
    import app as app_module
    import time
    now = time.time()
    return (
        session.get('admin') is True
        and session.get('auth_version') == app_module.ADMIN_AUTH_VERSION
        and isinstance(session.get('last_activity', 0), (int, float))
        and now - session.get('last_activity', 0) < app_module.ADMIN_SESSION_TIMEOUT
    )


def checkpoint_snapshot(team):
    db = ensure_participant_tables()
    rows = db.execute('''SELECT checkpoint_number FROM checkpoint_clears WHERE team_id=? ORDER BY checkpoint_number''', (team['id'],)).fetchall()
    cleared = {int(row['checkpoint_number']) for row in rows}
    finish = db.execute('''SELECT completed_at, elapsed_seconds FROM team_finishes WHERE team_id=?''', (team['id'],)).fetchone()
    return {
        'total': TOTAL_CHECKPOINTS,
        'cleared': sorted(cleared),
        'cleared_count': len(cleared),
        'completed': bool(finish),
        'completed_at': finish['completed_at'] if finish else None,
        'elapsed_seconds': finish['elapsed_seconds'] if finish else None,
    }


def scanner_security_headers(response):
    response.headers['Permissions-Policy'] = 'camera=(self), microphone=(), geolocation=(), display-capture=(), speaker-selection=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    return response


@app.after_request
def apply_participant_security_headers(response):
    response.headers.setdefault('Permissions-Policy', 'camera=(self), microphone=(), geolocation=(), display-capture=(), speaker-selection=()')
    return response


@app.route('/scan')
def participant_scan():
    team = get_team_from_cookie()
    if not team:
        return render_template('message.html', title='Event Access Restricted', message=DENIED_MESSAGE), 403
    wrapped = app.make_response(render_template(
        'scanner.html',
        team_number=team['team_number'],
        team_name=team['name'],
        progress=checkpoint_snapshot(team),
        total_checkpoints=TOTAL_CHECKPOINTS,
    ))
    return scanner_security_headers(wrapped)


@app.route('/api/participant/progress')
def participant_progress():
    team = get_team_from_cookie()
    if not team:
        return jsonify({'ok': False, 'message': DENIED_MESSAGE}), 403
    return jsonify({'ok': True, 'team_number': team['team_number'], 'progress': checkpoint_snapshot(team)})


@app.route('/api/participant/scan', methods=['POST'])
def participant_scan_result():
    team = get_team_from_cookie()
    if not team:
        return jsonify({'ok': False, 'message': DENIED_MESSAGE}), 403

    payload = request.get_json(silent=True) or {}
    route = str(payload.get('route', '')).strip()
    if route not in ALL_EVENT_ROUTES:
        return jsonify({'ok': False, 'message': 'Unsupported QR. Please scan an official event QR.'}), 400

    # Only the validated route name reaches the server. Camera frames never do.
    record_live_scan(route, team)
    db = ensure_participant_tables()

    if route in FAKE_ROUTES:
        return jsonify({
            'ok': True,
            'kind': 'bait',
            'route': route,
            'message': MESSAGES[route],
            'keyword': KEYWORDS.get(route, ROUTE_LABELS[route]),
            'progress': checkpoint_snapshot(team),
        })

    checkpoint_number = CHECKPOINT_MAP[route]
    existing = db.execute('''SELECT id FROM checkpoint_clears WHERE team_id=? AND checkpoint_number=?''', (team['id'], checkpoint_number)).fetchone()
    newly_cleared = False
    cleared_at = None
    if not existing:
        cleared_at = datetime.now(timezone.utc)
        db.execute('''
            INSERT INTO checkpoint_clears (team_id, team_number, checkpoint_number, route, cleared_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (team['id'], team['team_number'], checkpoint_number, route, cleared_at.isoformat()))
        db.commit()
        newly_cleared = True

    progress = checkpoint_snapshot(team)
    if progress['cleared_count'] >= TOTAL_CHECKPOINTS and not progress['completed']:
        first_valid = db.execute('''SELECT MIN(cleared_at) AS first_cleared FROM checkpoint_clears WHERE team_id=?''', (team['id'],)).fetchone()
        first_dt = datetime.fromisoformat(first_valid['first_cleared']) if first_valid and first_valid['first_cleared'] else cleared_at
        finish_dt = datetime.now(timezone.utc)
        elapsed = max(0.0, (finish_dt - first_dt).total_seconds())
        db.execute('''INSERT INTO team_finishes (team_id, team_number, completed_at, elapsed_seconds) VALUES (?, ?, ?, ?)''', (team['id'], team['team_number'], finish_dt.isoformat(), elapsed))
        db.commit()
        progress = checkpoint_snapshot(team)

    return jsonify({
        'ok': True,
        'kind': 'valid',
        'route': route,
        'checkpoint': checkpoint_number,
        'message': MESSAGES[route],
        'keyword': KEYWORDS[route],
        'newly_cleared': newly_cleared,
        'progress': progress,
    })


@app.route('/admin/participant-stats')
def admin_participant_stats():
    if not admin_session_active():
        return jsonify({'ok': False}), 401
    db = ensure_participant_tables()
    rows = db.execute('''
        SELECT t.team_number, t.name,
               COUNT(DISTINCT c.checkpoint_number) AS cleared_count,
               f.completed_at, f.elapsed_seconds
        FROM teams t
        LEFT JOIN checkpoint_clears c ON c.team_id=t.id
        LEFT JOIN team_finishes f ON f.team_id=t.id
        WHERE t.active=1
        GROUP BY t.id
        ORDER BY CASE WHEN f.completed_at IS NULL THEN 1 ELSE 0 END,
                 f.elapsed_seconds ASC, cleared_count DESC, t.team_number ASC
    ''').fetchall()
    return jsonify({
        'ok': True,
        'total_checkpoints': TOTAL_CHECKPOINTS,
        'teams': [
            {
                'team_number': row['team_number'],
                'name': row['name'],
                'cleared_count': row['cleared_count'],
                'completed': bool(row['completed_at']),
                'completed_at': row['completed_at'],
                'elapsed_seconds': row['elapsed_seconds'],
            }
            for row in rows
        ],
    })
