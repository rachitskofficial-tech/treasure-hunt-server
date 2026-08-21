"""Temporary kill-switch for all clue QR routes.

This keeps the existing clue code in place so it can be re-enabled later,
but makes every clue/test-clue URL unavailable until this module is removed
or the before_request guard is changed.
"""
from flask import abort, request

CLUE_PREFIXES = (
    '/clue',
    '/test/clue',
    '/event/clue',
)


def _block_clues():
    path = request.path.rstrip('/') or '/'
    if any(path == prefix or path.startswith(prefix + '/') for prefix in CLUE_PREFIXES):
        abort(404)


def register(app):
    app.before_request(_block_clues)


register(__import__('app').app)
