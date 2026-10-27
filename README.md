# Spotter — weather-aware truck routing

React + TypeScript map application with a Django REST backend. Compares routes using arrival-time forecasts, load-aware weather rules, and distance-weighted exposure. Includes a 0–48 hour corridor forecast and an explicitly labeled synthetic demo.

## Local setup

Requires Node 22+ and Python 3.12+.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
npm ci
npm run build
.venv\Scripts\python manage.py collectstatic --noinput
.venv\Scripts\python manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000. The initial demo works without provider keys. In development, run `npm run dev` in another terminal for Vite hot reload at port 5173; `/api` proxies to Django on port 8000.

On macOS/Linux replace `.venv\Scripts\python` with `.venv/bin/python`.

## Use

1. Explore the Chicago–Nashville demo, select route options, and click checkpoint dots on the map.
2. Change load and checkpoint spacing, then click **Find the best route** to recompute.
3. Use the forecast slider or play button to browse the corridor. Route risk stays tied to checkpoint arrival times.
4. Choose **Live journey**, resolve both places using search results, choose a departure within six days, and submit. Forecast coverage must include every arrival and the full 48-hour slider.
5. Open **How risk works** for thresholds, load overrides, recommendation order, and limitations.

Departure is explicitly entered in the browser's local timezone and transmitted as a UTC instant. It is not inferred from origin. The UI labels this choice to avoid timezone ambiguity.

## Architecture

- `backend/domain.py`: pure spherical interpolation, cumulative segment ETAs, weather rules, interval exposure, and deterministic recommendation.
- `backend/providers.py`: Photon geocoding, OSRM/optional Mapbox directions, Open-Meteo forecasts, and synthetic demo fixtures.
- `backend/views.py`: input validation, bounded analysis, separately loaded corridor frames, and expiring cached analysis IDs.
- `src/main.tsx`: trip form, typed API handling, comparison panel, MapLibre layers, checkpoint inspector, forecast controls, and methodology dialog.
- `src/types.ts`: explicit response/unit contracts.
- `src/style.css`: responsive layout, accessible colors/labels, and reduced-motion support.

The backend owns all risk calculations. Route intervals use the more restrictive endpoint category and their actual length, including the last partial interval. Unknown remains separate. Blocked and incomplete routes are excluded from recommendation. Eligible routes compare lexicographically: Severe miles, High miles, distance-weighted average category, then travel time. No weighted shortcut trades Severe exposure for speed.

## Assumptions and limits

- Shared rain/snow boundaries use the higher category except the explicitly strict upper No Travel thresholds. Rain exactly 1 in/hr and snow exactly 3 in/hr remain Severe.
- Wind uses continuous bands [25,35), [35,45), [45,55), and >=55 mph. Load overrides use strict >30,000 and >40,000 lb.
- Sustained wind is interpolated in time; hourly rain plus showers and snowfall use the hour-ending accumulation containing the ETA. Units normalize to mph and inches/hour.
- A checkpoint's missing required weather makes it Unknown. A partial comparison is explicitly qualified. No safe values are invented after provider failures.
- Sampling can miss conditions between checkpoints; conservative endpoint attribution can overstate an isolated hazard. Driving time excludes rest stops.
- The demo uses **illustrative corridors**, synthetic weather, and fixture driving times. It is not a road-navigation dataset. It is labeled throughout the UI.
- Live OSRM routes use automotive profiles and estimated durations without departure-time traffic. Optional Mapbox uses its driving-traffic profile. Neither configuration certifies truck clearance, axle restrictions, hazardous-material suitability, or road safety.
- A provider may return fewer than three genuine alternatives; the UI reports the actual count. No duplicates are generated.
- Maximum route length is 2,000 miles. Corridor cells are approximately 25 miles from a densified route union, capped at 120 locations. Effective grid resolution is disclosed; it may be coarse for large trips. Forecast cells depict sampled intensity, not radar or exact hazard boundaries.
- The corridor has 49 hourly frames relative to departure. Changing it never changes route ranking.
- The initial implementation uses Django's process-local cache, 15-minute analysis expiry and short forecast caching. Restarting loses analyses. The supplied container runs one threaded worker. Use Redis/shared cache before multiple workers or replicas.
- No account/history database, task queue, or persistence is required for this version. Large live analyses may take provider-dependent time; route results are independent of corridor loading.

## Provider configuration

Use `.env.example` as a reference. Environment variables are read from the process; `.env` is not loaded automatically. Set `MAPBOX_TOKEN` for Mapbox routing, or `ROUTING_BASE_URL` for your own OSRM-compatible provider. Keys stay server-side.

The no-key defaults use public OSRM and Photon demonstration services. Check applicable usage policies before sustained hosted traffic; replace demonstration services with an appropriate provider. The map uses OpenFreeMap's Positron vector basemap with its required attribution. Open-Meteo usage/licensing must fit the hosting purpose. Forecast requests are batched in groups of 25 with at most three concurrent workers; HTTP connect/read timeouts are bounded. Provider errors are surfaced without automatic fallbacks to fake data.

Official references: [OSRM API](https://project-osrm.org/docs/v5.24.0/api/), [Photon](https://photon.komoot.io/), [Open-Meteo forecast](https://open-meteo.com/en/docs), [Mapbox directions](https://docs.mapbox.com/api/navigation/directions/), [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/).

## Verification

```powershell
npm run build
.venv\Scripts\python manage.py check
.venv\Scripts\python -m pytest -q
```

Tests cover all hazard boundaries, strict load overrides, partial intervals, nonuniform segment ETAs, exposure totals, blocked/unknown recommendations, weather time/unit normalization, validation, full demo analysis, 49 corridor frames, expired IDs, fewer alternatives, and live-provider failure behavior. CI runs the same checks on Python 3.12 and Node 22.

## Hosting

Build and run the provided container:

```text
docker build -t spotter .
docker run --rm -p 8000:8000 -e DJANGO_SECRET_KEY=<random-secret> -e DJANGO_ALLOWED_HOSTS=<your-host> spotter
```

The same Django service serves the compiled frontend and API. Configure HTTPS on your container host/reverse proxy. Set a strong secret, explicit hostnames, and provider credentials where needed. The host health check is `GET /api/health`. For a single service deployment the default one-worker configuration preserves analysis cache consistency. Do not scale workers/replicas without a shared cache. `DJANGO_DEBUG=0` is the container default.

No hosted URL, GitHub remote, or Loom link is claimed until it exists. The source, container configuration, and walkthrough script are supplied locally. GitHub publishing requires an authenticated account/remote; hosting requires a compatible container destination; Loom requires recording access.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the full plan and [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md) for the recording script.
