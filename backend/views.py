import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from django.conf import settings
from django.core.cache import cache
from django.http import FileResponse, HttpResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import serializers
from . import domain, providers


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=300)
    coordinates = serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2)

    def validate_coordinates(self, value):
        if not all(math.isfinite(x) for x in value) or not (-180 <= value[0] <= 180 and -85 <= value[1] <= 85):
            raise serializers.ValidationError('Coordinates are outside the supported range.')
        return value


class AnalysisSerializer(serializers.Serializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    departure = serializers.DateTimeField()
    load_lb = serializers.FloatField(min_value=0, max_value=200000)
    spacing_miles = serializers.ChoiceField(choices=[10,25,50])
    mode = serializers.ChoiceField(choices=['demo','live'], default='demo')

    def validate(self, data):
        if not math.isfinite(data['load_lb']):
            raise serializers.ValidationError('Load must be a finite number.')
        raw = self.initial_data.get('departure', '')
        if not isinstance(raw, str) or not (raw.endswith('Z') or '+' in raw[10:] or '-' in raw[10:]):
            raise serializers.ValidationError('Departure requires an explicit UTC offset.')
        if data['mode'] == 'live':
            now = datetime.now(timezone.utc)
            if not now-timedelta(minutes=10) <= data['departure'] <= now+timedelta(days=6):
                raise serializers.ValidationError('Live departure must be within the next six days.')
            if domain.distance(data['origin']['coordinates'], data['destination']['coordinates']) < 100:
                raise serializers.ValidationError('Choose different origin and destination places.')
        return data


@api_view(['GET'])
def health(request):
    return Response({'status': 'ok', 'version': '1.0.0'})


@api_view(['GET'])
def place_search(request):
    query = request.query_params.get('q', '').strip()
    if len(query) < 3:
        return Response([])
    try:
        return Response(providers.places(query[:150]))
    except providers.ProviderError as exc:
        return Response({'error': str(exc)}, status=502)


@api_view(['POST'])
def analyze(request):
    serializer = AnalysisSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    demo = data['mode'] == 'demo'
    departure = data['departure']
    if demo:
        data['origin'], data['destination'] = providers.DEMO_ORIGIN, providers.DEMO_DESTINATION
    try:
        routes = providers.demo_routes() if demo else providers.routes(data['origin']['coordinates'], data['destination']['coordinates'], departure)
        if any(r['distance_miles'] > 2000 for r in routes):
            return Response({'error': 'This version supports routes up to 2,000 miles. Choose a shorter trip.'}, status=400)
        end = departure+timedelta(seconds=max(48*3600, max(r['duration_seconds'] for r in routes)))
        if not demo and end > datetime.now(timezone.utc)+timedelta(days=7):
            return Response({'error': 'The full trip and 48-hour slider exceed the supported forecast horizon.'}, status=400)
        all_points = []
        for route in routes:
            route['checkpoints'] = domain.checkpoints(route, data['spacing_miles'], departure)
            all_points.extend(route['checkpoints'])
        forecasts = None if demo else providers.fetch_forecasts([p['coordinates'] for p in all_points], departure, end)
        for i, point in enumerate(all_points):
            instant = datetime.fromisoformat(point['eta'])
            weather = providers.demo_weather(point['coordinates'], instant) if demo else providers.at_time(forecasts[i], instant)
            point['weather'] = weather
            point['risk'] = domain.risk(weather['wind_mph'], weather['rain_in_hr'], weather['snow_in_hr'], data['load_lb'])
        for route in routes:
            route['summary'] = domain.summarize(route['checkpoints'])
            del route['segment_distances'], route['segment_durations']
        recommended, ranked, reason = domain.recommend(routes)
        analysis_id = uuid.uuid4().hex
        warnings = ['Illustrative demo: synthetic weather, estimated corridors and driving times.'] if demo else ['Automotive routes do not assess truck clearance, axle limits, or rest stops.']
        if len(routes) < 3:
            warnings.append(f'The provider found {len(routes)} distinct route(s); three are not available for this journey.')
        result = {'id': analysis_id, 'mode': data['mode'], 'origin': data['origin'], 'destination': data['destination'], 'departure': departure.isoformat(), 'load_lb': data['load_lb'], 'spacing_miles': data['spacing_miles'], 'routes': routes, 'recommended_id': recommended, 'ranked_ids': ranked, 'reason': reason, 'warnings': warnings, 'policy_version': '1.0', 'fetched_at': datetime.now(timezone.utc).isoformat(), 'expires_at': (datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat()}
        cache.set('analysis:'+analysis_id, result, 900)
        return Response(result)
    except providers.ProviderError as exc:
        return Response({'error': str(exc)}, status=502)
    except ValueError as exc:
        return Response({'error': str(exc)}, status=422)
    except (KeyError, TypeError, IndexError):
        return Response({'error': 'A provider returned an invalid response. This journey could not be assessed.'}, status=502)


@api_view(['GET'])
def corridor(request, analysis_id):
    result = cache.get('corridor:'+analysis_id)
    if result is not None:
        return Response(result)
    analysis = cache.get('analysis:'+analysis_id)
    if analysis is None:
        return Response({'error': 'Analysis expired. Analyze the trip again.'}, status=410)
    # Create uniform spatial cells near the route union, not its whole bounding box.
    route_points = [p['coordinates'] for r in analysis['routes'] for p in r['checkpoints']]
    lat0, lat1 = min(p[1] for p in route_points)-.3, max(p[1] for p in route_points)+.3
    lon0, lon1 = min(p[0] for p in route_points)-.4, max(p[0] for p in route_points)+.4
    step = .20
    def grid(step):
        cells = []
        lat = lat0
        while lat <= lat1:
            lon = lon0
            while lon <= lon1:
                p = [round(lon,5), round(lat,5)]
                # Distance to a densified route chain, independent of chosen sampling interval.
                if any(domain.distance(p, q) <= 40234 for q in dense):
                    cells.append(p)
                lon += step/max(.2, math.cos(math.radians(lat)))
            lat += step
        return cells
    dense = []
    for r in analysis['routes']:
        for a, b in zip(r['coordinates'], r['coordinates'][1:]):
            n = max(1, math.ceil(domain.distance(a,b)/15000))
            dense.extend(domain.interpolate(a,b,i/n) for i in range(n+1))
    # Bound grid generation and geographic work for long routes.
    step = max(step, math.sqrt(max(.01,(lat1-lat0)*(lon1-lon0))/150))
    cells = grid(step)
    while len(cells) > 120:
        step *= 1.25
        cells = grid(step)
    start = datetime.fromisoformat(analysis['departure'])
    times = [start+timedelta(hours=h) for h in range(49)]
    try:
        forecasts = None if analysis['mode'] == 'demo' else providers.fetch_forecasts(cells, start, times[-1])
        frames = []
        for instant in times:
            values = []
            for i, cell in enumerate(cells):
                w = providers.demo_weather(cell, instant) if forecasts is None else providers.at_time(forecasts[i], instant)
                values.append({'wind': w['wind_mph'], 'rain': w['rain_in_hr'], 'snow': w['snow_in_hr'], 'risk': domain.risk(w['wind_mph'], w['rain_in_hr'], w['snow_in_hr'], analysis['load_lb'])['score']})
            frames.append(values)
        result = {'coordinates': cells, 'frames': frames, 'times': [t.isoformat() for t in times], 'resolution_miles': step*69, 'width_miles': 25, 'mode': analysis['mode']}
        cache.set('corridor:'+analysis_id, result, 600)
        return Response(result)
    except providers.ProviderError as exc:
        return Response({'error': str(exc)}, status=502)


def frontend(request):
    index = Path(settings.BASE_DIR)/'dist'/'index.html'
    if index.exists():
        return FileResponse(index.open('rb'), content_type='text/html')
    return HttpResponse('Run npm run build, or open the Vite development server on port 5173.', status=503)
