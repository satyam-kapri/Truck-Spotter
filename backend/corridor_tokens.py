"""Signed trip context for corridor requests that may reach another instance."""
from django.core import signing
from .domain import distance

TOKEN_SALT = 'spotter.corridor.v1'
TOKEN_TTL_SECONDS = 900


def compact_geometry(coordinates):
    # Only the coarse weather corridor uses this geometry. Exact route geometry,
    # checkpoint ETAs, and all risk/recommendation calculations are unchanged.
    kept = [coordinates[0]]
    for point in coordinates[1:-1]:
        if distance(kept[-1], point) >= 1000:
            kept.append(point)
    if kept[-1] != coordinates[-1]:
        kept.append(coordinates[-1])
    return [[round(lon, 5), round(lat, 5)] for lon, lat in kept]


def make_corridor_token(analysis):
    payload = {
        'version': 1,
        'id': analysis['id'],
        'mode': analysis['mode'],
        'departure': analysis['departure'],
        'load_lb': analysis['load_lb'],
        'routes': [compact_geometry(route['coordinates']) for route in analysis['routes']],
    }
    return signing.dumps(payload, salt=TOKEN_SALT, compress=True)


def read_corridor_token(token, analysis_id):
    payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_TTL_SECONDS)
    if payload.get('version') != 1 or payload.get('id') != analysis_id:
        raise signing.BadSignature('Trip token does not match this analysis.')
    return {
        'id': payload['id'], 'mode': payload['mode'],
        'departure': payload['departure'], 'load_lb': payload['load_lb'],
        'routes': [{'coordinates': coordinates} for coordinates in payload['routes']],
    }
