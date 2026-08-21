import app as app_module

FAKE_MESSAGES = {
    'wrong4': 'Nice try 😏 That QR is fake. Keep searching.',
    'wrong5': 'Not this one 😅 Keep looking around.',
    'wrong6': 'Close... but nope. 🔎 Find the real checkpoint.',
    'wrong7': 'Plot twist 😈 Wrong QR. The hunt continues.',
}

FAKE_LABELS = {
    'wrong4': 'Wrong QR 4',
    'wrong5': 'Wrong QR 5',
    'wrong6': 'Wrong QR 6',
    'wrong7': 'Wrong QR 7',
}

FAKE_KEYWORDS = {
    'wrong4': 'Nice Try',
    'wrong5': 'Keep Looking',
    'wrong6': 'Not Here',
    'wrong7': 'Plot Twist',
}

# Extend the live-event registry before participant.py imports these values.
app_module.MESSAGES.update(FAKE_MESSAGES)
app_module.ROUTE_LABELS.update(FAKE_LABELS)
app_module.KEYWORDS.update(FAKE_KEYWORDS)

# Keep these as ordered tuples and de-duplicate them so the admin dashboard
# and participant scanner always see all seven fake QR routes.
app_module.FAKE_ROUTES = tuple(dict.fromkeys(app_module.FAKE_ROUTES + tuple(FAKE_MESSAGES)))
app_module.ROUTES = tuple(dict.fromkeys(app_module.ROUTES + tuple(FAKE_MESSAGES)))


def _live_fake_scan(route):
    team = app_module.get_team_from_cookie()
    if not team:
        return app_module.team_gate_response()
    app_module.record_live_scan(route, team)
    return app_module.render_template(
        'message.html',
        title=app_module.ROUTE_LABELS[route],
        message=app_module.MESSAGES[route],
    )


# Primary live QR endpoints.
@app_module.app.route('/event/wrong4')
def event_wrong4():
    return _live_fake_scan('wrong4')


@app_module.app.route('/event/wrong5')
def event_wrong5():
    return _live_fake_scan('wrong5')


@app_module.app.route('/event/wrong6')
def event_wrong6():
    return _live_fake_scan('wrong6')


@app_module.app.route('/event/wrong7')
def event_wrong7():
    return _live_fake_scan('wrong7')


# Direct aliases are supported as well, so a QR containing /wrong4 ... /wrong7
# still records a live scan instead of falling into a sandbox-only route.
@app_module.app.route('/wrong4')
def direct_wrong4():
    return _live_fake_scan('wrong4')


@app_module.app.route('/wrong5')
def direct_wrong5():
    return _live_fake_scan('wrong5')


@app_module.app.route('/wrong6')
def direct_wrong6():
    return _live_fake_scan('wrong6')


@app_module.app.route('/wrong7')
def direct_wrong7():
    return _live_fake_scan('wrong7')
