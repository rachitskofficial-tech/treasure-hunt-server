import secrets
import sqlite3
from datetime import datetime, timezone
from flask import make_response, render_template, request

from app import app, TEAM_COOKIE, TEAM_SLOTS, get_db, get_team_from_cookie, hash_value, new_temp_id


def _remove_endpoint(endpoint):
    rules = [rule for rule in list(app.url_map.iter_rules()) if rule.endpoint == endpoint]
    for rule in rules:
        app.url_map._rules.remove(rule)
        bucket = app.url_map._rules_by_endpoint.get(endpoint, [])
        if rule in bucket:
            bucket.remove(rule)
    app.url_map.update()


_remove_endpoint('register_team')


@app.route('/register', methods=['GET', 'POST'], endpoint='register_team_clean')
def register_team_clean():
    db = get_db()
    error = None
    current = get_team_from_cookie()
    if current:
        return render_template('register.html', success=True, temp_id='ALREADY REGISTERED', team_number=current['team_number'], available_teams=[])

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        contact = request.form.get('contact', '').strip()
        team_raw = request.form.get('team_number', '').strip()
        try:
            team_number = int(team_raw)
        except ValueError:
            team_number = 0

        if not name or not contact or team_number not in TEAM_SLOTS:
            error = 'Please complete all fields and choose a valid team number.'
        elif db.execute('SELECT id FROM teams WHERE team_number=? AND active=1', (team_number,)).fetchone():
            error = f'Team {team_number} is already registered. Please choose another team.'
        else:
            raw_token = secrets.token_hex(32)
            temp_id = new_temp_id(team_number)
            try:
                db.execute('''INSERT INTO teams
                    (team_number, name, uucms_number, contact_number, temp_id_hash, device_token_hash, registered_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (team_number, name, '', contact, hash_value(temp_id), hash_value(raw_token), datetime.now(timezone.utc).isoformat()))
                db.commit()
                response = make_response(render_template('register.html', success=True, temp_id=temp_id, team_number=team_number, available_teams=[]))
                response.set_cookie(TEAM_COOKIE, raw_token, max_age=48 * 60 * 60, httponly=True, samesite='Lax', secure=request.is_secure)
                return response
            except sqlite3.IntegrityError:
                db.rollback()
                error = 'That team could not be registered. Please try another team.'

    available = [n for n in TEAM_SLOTS if not db.execute('SELECT 1 FROM teams WHERE team_number=? AND active=1', (n,)).fetchone()]
    return render_template('register.html', success=False, temp_id=None, team_number=None, available_teams=available, error=error)
