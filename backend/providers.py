"""Provider adapters. No live-data failure is replaced with synthetic weather."""
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import requests
from django.core.cache import cache
from .domain import distance, risk


class ProviderError(Exception):
    pass


def get_json(url, params=None):
    try:
        response = requests.get(url, params=params, timeout=(5, 20), headers={'User-Agent': 'SpotterRouting/1.0'})
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise ProviderError('An external provider is unavailable or rate limited. Please try again shortly.') from exc


def places(query):
    key = 'places:'+query.strip().lower()
    saved = cache.get(key)
    if saved is not None:
        return saved
    data = get_json('https://photon.komoot.io/api/', {'q': query, 'limit': 5, 'lang': 'en'})
    result = []
    for feature in data.get('features', []):
        p = feature['properties']
        label = ', '.join(dict.fromkeys(str(p[k]) for k in ['name', 'city', 'state', 'country'] if p.get(k)))
        result.append({'label': label, 'coordinates': feature['geometry']['coordinates']})
    cache.set(key, result, 3600)
    return result


def routes(origin, destination, departure):
    pair = ';'.join(','.join(map(str, p)) for p in [origin, destination])
    token = os.environ.get('MAPBOX_TOKEN')
    if token:
        url = f'https://api.mapbox.com/directions/v5/mapbox/driving-traffic/{pair}'
        params = {'access_token': token, 'alternatives': 'true', 'annotations': 'distance,duration', 'overview': 'full', 'geometries': 'geojson', 'depart_at': departure.isoformat()}
        provider = 'Mapbox driving-traffic'
    else:
        base = os.environ.get('ROUTING_BASE_URL', 'https://router.project-osrm.org').rstrip('/')
        url = f'{base}/route/v1/driving/{pair}'
        params = {'alternatives': 2, 'annotations': 'distance,duration', 'overview': 'full', 'geometries': 'geojson'}
        provider = 'OSRM driving (estimated duration; no departure traffic)'
    data = get_json(url, params)
    if data.get('code') != 'Ok' or not data.get('routes'):
        raise ProviderError('No drivable route was found for these places.')
    result, seen = [], set()
    for r in data['routes']:
        coords = r['geometry']['coordinates']
        fingerprint = tuple(tuple(p) for p in coords)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        # These APIs have different geometry/annotation alignment conventions.
        # When not one-to-one, use leg step geometry with maneuver durations.
        ds = [d for leg in r['legs'] for d in leg.get('annotation', {}).get('distance', [])]
        ts = [t for leg in r['legs'] for t in leg.get('annotation', {}).get('duration', [])]
        timing = 'provider segment durations'
        if len(ds) != len(coords)-1 or len(ts) != len(ds):
            raise ProviderError('Route geometry does not align with timing annotations; this route cannot be assessed accurately.')
        result.append({'id': f'route-{len(result)+1}', 'name': ['Primary route', 'Alternative route', 'Third route'][len(result)], 'coordinates': coords, 'segment_distances': ds, 'segment_durations': ts, 'distance_miles': sum(ds)/1609.344, 'duration_seconds': sum(ts), 'provider': provider, 'timing': timing})
        if len(result) == 3:
            break
    return result


def fetch_forecasts(coordinates, start, end):
    """Exact coordinates, UTC hourly series, bounded batched concurrency."""
    def batch(points):
        key = 'weather:'+hashlib.sha256(repr((points, start.date().isoformat(), end.date().isoformat())).encode()).hexdigest()
        saved = cache.get(key)
        if saved is not None:
            return saved
        data = get_json('https://api.open-meteo.com/v1/forecast', {
            'latitude': ','.join(str(p[1]) for p in points), 'longitude': ','.join(str(p[0]) for p in points),
            'hourly': 'wind_speed_10m,rain,showers,snowfall', 'wind_speed_unit': 'mph',
            'timezone': 'GMT', 'start_date': start.date().isoformat(),
            'end_date': (end+timedelta(hours=1)).date().isoformat(),
        })
        data = data if isinstance(data, list) else [data]
        if len(data) != len(points):
            raise ProviderError('Weather provider returned an incomplete location batch.')
        for item in data:
            units = item.get('hourly_units', {})
            if any(units.get(k) != unit for k, unit in [('wind_speed_10m', 'mp/h'), ('rain', 'mm'), ('showers', 'mm'), ('snowfall', 'cm')]):
                raise ProviderError('Weather provider returned unexpected units.')
        cache.set(key, data, 900)
        return data
    batches = [coordinates[i:i+25] for i in range(0, len(coordinates), 25)]
    with ThreadPoolExecutor(max_workers=3) as executor:
        return [item for group in executor.map(batch, batches) for item in group]


def at_time(series, instant):
    hourly = series.get('hourly', {})
    times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in hourly.get('time', [])]
    def unknown():
        return {'wind_mph': None, 'rain_in_hr': None, 'snow_in_hr': None, 'forecast_time': None}
    if not times or instant < times[0] or instant > times[-1]:
        return unknown()
    from bisect import bisect_left
    hi = bisect_left(times, instant)
    lo = max(0, hi-1)
    try:
        w0, w1 = hourly['wind_speed_10m'][lo], hourly['wind_speed_10m'][hi]
        rain, showers, snow = (hourly[k][hi] for k in ('rain', 'showers', 'snowfall'))
        if any(x is None for x in (w0, w1, rain, showers, snow)):
            return unknown()
        f = (instant-times[lo]).total_seconds()/max(1, (times[hi]-times[lo]).total_seconds())
        return {'wind_mph': w0+(w1-w0)*f, 'rain_in_hr': (rain+showers)/25.4, 'snow_in_hr': snow/2.54, 'forecast_time': times[hi].isoformat()}
    except (IndexError, KeyError, TypeError):
        return unknown()


DEMO_ORIGIN = {'label': 'Chicago, Illinois', 'coordinates': [-87.6298, 41.8781]}
DEMO_DESTINATION = {'label': 'Nashville, Tennessee', 'coordinates': [-86.7816, 36.1627]}


def demo_routes():
    # Illustrative corridors, deliberately not represented as turn-by-turn road geometry.
    options = [
        ('I-65 · via Indianapolis', [[-87.6298,41.8781],[-87.32,41.5],[-87.0,41.0],[-86.5,40.4],[-86.158,39.768],[-85.9,39.0],[-85.759,38.253],[-86.0,37.5],[-86.45,36.99],[-86.7816,36.1627]], 510, 8.2),
        ('I-57 / I-24 · via Paducah', [[-87.6298,41.8781],[-87.7,41.2],[-87.9,40.5],[-88.24,40.116],[-88.3,39.3],[-88.93,38.3],[-88.97,37.73],[-88.6,37.08],[-87.48,36.86],[-86.7816,36.1627]], 535, 8.65),
        ('I-55 / I-24 · via St. Louis', [[-87.6298,41.8781],[-88.08,41.52],[-89.0,40.7],[-89.65,39.78],[-90.199,38.627],[-89.6,38.3],[-88.97,37.73],[-88.6,37.08],[-87.48,36.86],[-86.7816,36.1627]], 620, 9.8),
    ]
    result = []
    for i, (name, coords, miles, hours) in enumerate(options):
        ds = [distance(a,b) for a,b in zip(coords,coords[1:])]
        scale = miles*1609.344/sum(ds)
        ds = [d*scale for d in ds]
        result.append({'id': f'route-{i+1}', 'name': name, 'coordinates': coords, 'segment_distances': ds, 'segment_durations': [d/sum(ds)*hours*3600 for d in ds], 'distance_miles': miles, 'duration_seconds': hours*3600, 'provider': 'Illustrative demo corridors', 'timing': 'Synthetic fixture duration'})
    return result


def demo_weather(coordinate, instant):
    lon, lat = coordinate
    hour = instant.hour + instant.minute/60
    # A moving weather system for a deterministic, clearly labeled demonstration.
    from math import sin
    center = -85.9 + .15*sin(hour/12)
    storm = math_exp(-((lon-center)/.60)**2-((lat-38.5)/1.15)**2)
    wind = 13+34*storm
    rain = .015+.35*storm
    return {'wind_mph': wind, 'rain_in_hr': rain, 'snow_in_hr': 0.0, 'forecast_time': instant.isoformat()}


def math_exp(x):
    from math import exp
    return exp(x)
