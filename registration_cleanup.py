"""Disable the retired public registration and participant scanner endpoints.

The underlying team/live-scan data model is intentionally left untouched so
existing event data and the admin control room continue to work.
"""

from app import app


RETIRED_ENDPOINTS = {
    # Public registration flow
    'register_team',
    'team_status',
    # Participant QR camera/scanner flow
    'participant_scan',
    'participant_progress',
    'participant_scan_result',
}

for endpoint in RETIRED_ENDPOINTS:
    app.view_functions.pop(endpoint, None)
