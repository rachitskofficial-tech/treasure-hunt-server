import os
import secrets
import time
from flask import request, session, redirect, render_template, make_response
import app as app_module

# Never ship a known admin password or a known Flask signing secret.
# Render should provide ADMIN_PASSWORD and SECRET_KEY as environment variables.
if not os.environ.get('SECRET_KEY'):
    app_module.app.secret_key = secrets.token_hex(32)
app_module.app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_NAME='niks_admin_session',
)

_LOGIN_WINDOW = 600
_MAX_FAILURES = 5
_failures = {}

def _client_key():
    return (request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip() or 'unknown')

def _prune():
    now = time.time()
    for key, attempts in list(_failures.items()):
        attempts[:] = [stamp for stamp in attempts if now - stamp < _LOGIN_WINDOW]
        if not attempts:
            _failures.pop(key, None)

def secure_admin_login():
    _prune()
    key = _client_key()
    attempts = _failures.setdefault(key, [])
    retry_after = 0
    if len(attempts) >= _MAX_FAILURES:
        retry_after = max(1, int(_LOGIN_WINDOW - (time.time() - attempts[0])))
    error = None
    if request.method == 'POST':
        if retry_after:
            error = f'Too many attempts. Try again in about {retry_after // 60 + 1} minute(s).'
        else:
            configured_password = os.environ.get('ADMIN_PASSWORD')
            supplied = request.form.get('password', '')
            if configured_password and secrets.compare_digest(supplied, configured_password):
                session.clear()
                session['admin'] = True
                session['auth_version'] = app_module.ADMIN_AUTH_VERSION
                session['last_activity'] = time.time()
                response = make_response(redirect('/admin'))
                response.headers['Cache-Control'] = 'no-store'
                return response
            attempts.append(time.time())
            error = 'Incorrect password.' if configured_password else 'Admin login is temporarily unavailable. Set ADMIN_PASSWORD in the server environment.'
    response = make_response(render_template('login.html', error=error))
    response.headers['Cache-Control'] = 'no-store'
    return response

app_module.app.view_functions['admin_login'] = secure_admin_login

@app_module.app.after_request
def security_headers(response):
    if request.path.startswith('/admin') or request.path.startswith('/event/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'same-origin'
    return response
