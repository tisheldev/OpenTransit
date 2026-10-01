"""Shared request logger; never log bodies, coordinates or query strings."""

import logging

LOG = logging.getLogger("opentransit.requests")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    LOG.addHandler(logging.StreamHandler())
