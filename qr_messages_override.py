from flask import jsonify, request, redirect
from app import app, get_db, admin_required, MESSAGES, ROUTES, ROUTE_LABELS, get_team_from_cookie, record_live_scan, team_gate_response


def ensure_qr_messages():
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS qr_messages (route TEXT PRIMARY KEY, message TEXT NOT NULL)')
    for route in ROUTES:
        db.execute('INSERT OR IGNORE INTO qr_messages(route, message) VALUES (?, ?)', (route, MESSAGES.get(route, '')))
    db.commit()
    return db


def current_message(route):
    db = ensure_qr_messages()
    row = db.execute('SELECT message FROM qr_messages WHERE route=?', (route,)).fetchone()
    return row['message'] if row else MESSAGES.get(route, '')


@app.route('/admin/qr-messages', methods=['GET', 'POST'])
@admin_required
def admin_qr_messages():
    db = ensure_qr_messages()
    if request.method == 'POST':
        for route in ROUTES:
            if route in request.form:
                value = request.form.get(route, '').strip()
                if value:
                    db.execute('UPDATE qr_messages SET message=? WHERE route=?', (value, route))
        db.commit()
        return redirect('/admin')
    return jsonify({route: {'label': ROUTE_LABELS.get(route, route), 'message': current_message(route)} for route in ROUTES})


def live_event_scan_with_editable_message(route):
    team = get_team_from_cookie()
    if not team:
        return team_gate_response()
    record_live_scan(route, team)
    return __import__('flask').render_template('message.html', title=ROUTE_LABELS[route], message=current_message(route))

for _route in ROUTES:
    _endpoint = f'event_{_route}'
    if _endpoint in app.view_functions:
        app.view_functions[_endpoint] = (lambda route: (lambda: live_event_scan_with_editable_message(route)))(_route)
