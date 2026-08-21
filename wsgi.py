import app as app_module

from werkzeug.middleware.proxy_fix import ProxyFix

app = app_module.app
app_module.TEAM_SLOTS = tuple(range(1, 8))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Extend fake QR routes before participant.py snapshots the route constants.
import fake_routes  # noqa: E402,F401

# Register participant routes on the same Flask application.
import participant  # noqa: E402,F401

# Register isolated camera diagnostic route.
import camera_test  # noqa: E402,F401

# Replace the legacy registration handler with the UUCMS-free version.
import registration_override  # noqa: E402,F401

application = app
