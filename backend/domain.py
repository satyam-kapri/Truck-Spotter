"""Network-free geometry, weather rules, exposure accounting, and ranking."""
import math
from bisect import bisect_right
from datetime import timedelta

MILE = 1609.344
LEVELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel']


def risk(wind, rain, snow, load):
    if any(v is None for v in (wind, rain, snow)):
        return {'level': 'Unknown', 'score': None, 'reasons': ['Required forecast data is unavailable.']}
    if any(not math.isfinite(v) or v < 0 for v in (wind, rain, snow, load)):
        raise ValueError('Weather and load must be finite and nonnegative.')
    w = sum(wind >= x for x in (25, 35, 45, 55))
    r = 4 if rain > 1 else sum(rain >= x for x in (.10, .25, .50))
    s = 4 if snow > 3 else sum(snow >= x for x in (.5, 1, 2))
    reasons = []
    for label, value, unit, score in [('Wind', wind, 'mph', w), ('Rain', rain, 'in/hr', r), ('Snow', snow, 'in/hr', s)]:
        if score:
            reasons.append(f'{label} {value:.2f} {unit}: {LEVELS[score]}.')
    if 45 <= wind < 55 and load > 30000:
        w = 4
        reasons.append('WIND_LOAD_NO_TRAVEL: wind >=45 mph with load >30,000 lb.')
    elif 35 <= wind < 45 and load > 40000:
        w = max(w, 3)
        reasons.append('WIND_LOAD_SEVERE: wind >=35 mph with load >40,000 lb.')
    score = max(w, r, s)
    return {'level': LEVELS[score], 'score': score, 'reasons': reasons or ['All weather values are below the Moderate thresholds.']}


def distance(a, b):
    lon1, lat1, lon2, lat2 = map(math.radians, [*a, *b])
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371008.8 * 2 * math.asin(min(1, math.sqrt(h)))


def interpolate(a, b, f):
    # Spherical interpolation keeps checkpoints on the geodesic segment.
    def vector(p):
        lon, lat = map(math.radians, p)
        return (math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat))
    u, v = vector(a), vector(b)
    angle = math.acos(max(-1, min(1, sum(x*y for x, y in zip(u, v)))))
    if angle < 1e-10:
        return list(a)
    factors = math.sin((1-f)*angle)/math.sin(angle), math.sin(f*angle)/math.sin(angle)
    x, y, z = [factors[0]*i + factors[1]*j for i, j in zip(u, v)]
    return [math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))]


def checkpoints(route, spacing, departure):
    coords = route['coordinates']
    ds, ts = route['segment_distances'], route['segment_durations']
    if len(coords) < 2 or len(ds) != len(coords)-1 or len(ts) != len(ds):
        raise ValueError('Routing provider returned misaligned geometry annotations.')
    if any(not math.isfinite(x) or x < 0 for x in ds+ts) or sum(ds) <= 0:
        raise ValueError('Routing provider returned invalid distances or durations.')
    prefix, times = [0.0], [0.0]
    for d, t in zip(ds, ts):
        prefix.append(prefix[-1]+d)
        times.append(times[-1]+t)
    total = prefix[-1]
    points = [i*spacing*MILE for i in range(int(total/(spacing*MILE))+1)]
    if total-points[-1] > .01:
        points.append(total)
    else:
        points[-1] = total
    result = []
    for i, d in enumerate(points):
        idx = min(bisect_right(prefix, d)-1, len(ds)-1)
        f = (d-prefix[idx])/ds[idx] if ds[idx] else 0
        seconds = times[idx]+f*ts[idx]
        result.append({'id': i, 'segment_index': idx, 'coordinates': interpolate(coords[idx], coords[idx+1], f), 'mile': d/MILE, 'elapsed_seconds': seconds, 'eta': (departure+timedelta(seconds=seconds)).isoformat()})
    return result


def summarize(points):
    miles = {level: 0.0 for level in LEVELS+['Unknown']}
    intervals = []
    for a, b in zip(points, points[1:]):
        unknown = a['risk']['score'] is None or b['risk']['score'] is None
        level = 'Unknown' if unknown else LEVELS[max(a['risk']['score'], b['risk']['score'])]
        length = b['mile']-a['mile']
        miles[level] += length
        intervals.append({'from': a['id'], 'to': b['id'], 'miles': length, 'level': level})
    total = sum(miles.values())
    complete = miles['Unknown'] == 0
    blocked = any(p['risk']['level'] == 'No Travel' for p in points)
    avg = sum(miles[l]*i for i, l in enumerate(LEVELS))/total if complete and total else None
    return {'miles_by_risk': miles, 'average_risk': avg, 'complete': complete, 'blocked': blocked, 'intervals': intervals}


def recommend(routes):
    eligible = [r for r in routes if r['summary']['complete'] and not r['summary']['blocked']]
    def key(r):
        s = r['summary']
        return (s['miles_by_risk']['Severe'], s['miles_by_risk']['High'], s['average_risk'], r['duration_seconds'], r['id'])
    ranked = sorted(eligible, key=key)
    if not ranked:
        return None, [], 'No route recommended. Routes are blocked by the supplied rules or have incomplete forecasts.'
    why = 'Lowest exposure under the supplied weather rules.'
    if len(ranked) > 1:
        a, b = ranked[:2]
        for field, label in [('Severe', 'Severe'), ('High', 'High')]:
            delta = b['summary']['miles_by_risk'][field]-a['summary']['miles_by_risk'][field]
            if delta > 1e-7:
                why = f'{delta:.1f} fewer {label} miles than the next eligible route.'
                break
        else:
            why = 'Lowest distance-weighted risk, then shortest travel time.'
    if any(not r['summary']['complete'] for r in routes):
        why += ' Comparison is incomplete: one or more candidates lack forecast data.'
    return ranked[0]['id'], [r['id'] for r in ranked], why
