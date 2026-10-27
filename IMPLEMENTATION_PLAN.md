# Weather-Aware Truck Routing — Implementation Plan

Status: implementation-ready proposal; no application code has been built.

Source: `fs-assessment-spotter.pdf`, both pages, reviewed on 27 October 2026.

## 1. Outcome and scope

Build a React + Django application that compares three candidate routes using weather at the truck's estimated arrival time, applies the supplied weather/load rules, and explains its recommendation. Deliver a GitHub repository, a hosted application, and a 5–10 minute Loom walkthrough.

Allocate effort according to the evaluation: 40% route/weather/risk correctness, 40% map/UI/heatmap performance, 15% code quality, and 5% documentation and walkthrough. Establish a working vertical slice early; reserve explicit time for map performance and deployment.

Required scope:

- Origin and destination search, departure date/time, load in pounds, and checkpoint spacing of 10, 25, or 50 miles.
- Three distinct route options where the routing provider can supply them.
- Checkpoints with coordinates, distance, ETA, weather values, risk, and explanation.
- Route summaries with travel time, mileage by risk category, and recommendation rationale.
- All routes and checkpoints on an interactive map.
- A corridor weather heatmap with a 0–48 hour forecast slider.

Out of scope for this assessment: accounts, fleet management, payments, GPS tracking, turn-by-turn navigation, a custom routing engine, and automatic departure optimization. Truck height/axle/hazardous-material restrictions are a separate capability requiring vehicle inputs and an appropriate routing provider; load weight here affects the specified weather rules.

## 2. Resolve ambiguities explicitly

These are proposed product decisions, not additional requirements from the PDF. Record them in the README and encode them in tests. They do not block building the initial vertical slice.

| Issue | Proposed behavior |
|---|---|
| Overlapping rain/snow boundaries | Use the higher risk at shared interior boundaries: rain 0.25 is High and 0.50 is Severe; snow 1.0 is High and 2.0 is Severe. Preserve the explicit strict No Travel limits: rain exactly 1.00 and snow exactly 3.0 remain Severe. |
| Fractional wind speeds | Interpret printed integer ranges continuously: [25,35), [35,45), [45,55). Never round before classification. |
| Combining hazards | Overall checkpoint risk is the maximum of wind, rain, snow, and applicable load overrides. Retain every contributing reason. |
| No Travel and route ranking | Exclude a route containing any sampled No Travel exposure from recommendation. Still display it with the affected miles and reason. If every route is blocked, show “No route recommended.” |
| Missing forecasts | Unknown is a separate state, never Low. An incomplete route cannot be an unconditional recommendation. If any candidate is incomplete, qualify the comparison as incomplete even when recommending among fully assessed candidates. |
| Fewer than three alternatives | Show the actual count and an explanation. Never duplicate routes to satisfy a count. Validate demo journeys with three genuine options during the provider spike. |
| Slider reference time | 0h means the submitted departure instant; +48h is departure plus 48 hours. Display the absolute timestamp and timezone. Browsing the slider changes the corridor forecast only, not the departure or route ranking. |
| Average risk | Distance-weighted mean of ordinal scores Low=0, Moderate=1, High=2, Severe=3. No Travel is a separate exclusion; Unknown has no numeric score. |
| ETA | Continuous driving time from provider durations; no rest or refueling stops. Show this assumption beside travel time. |
| Forecast horizon | Accept a trip only when the provider covers all route ETAs and the full slider window. Do not clamp out-of-range times to the last available forecast. |
| “Safest” wording | Use “Recommended by supplied weather rules”; a sampled forecast assessment cannot certify road safety. |

## 3. Architecture and technology

Use a small monorepo with one frontend and one backend. Keep provider integration and domain calculations separate. No microservices, custom routing engine, or task queue in the first version.

| Area | Choice | Reason |
|---|---|---|
| Frontend | React, TypeScript, Vite | Typed UI with a straightforward build and deployment |
| Map | MapLibre GL JS, licensed production basemap | GPU-rendered route, point, and corridor layers |
| Server state | TanStack Query | Cache requests, cancel stale searches, handle retry/loading states |
| Backend | Django + Django REST Framework | Validated API and central provider orchestration |
| Geometry | Python geodesic helpers; GeoJSON contracts | Sample along actual routes and share renderable geometry |
| Cache | Django cache interface, shared Redis in hosting | Reuse forecasts and analyses across requests/workers |
| Persistence | No saved-trip model initially | Requirements do not require history; cached analyses are sufficient |
| Testing | pytest, frontend unit tests, Playwright | Deterministic domain verification plus complete browser journeys |
| Delivery | Containerized Django, static frontend, CI | Reproducible local setup and hosting |

Request flow:

1. React submits resolved places, departure instant, load, and spacing.
2. Django fetches routes through a routing adapter.
3. Geometry service derives checkpoints and ETAs.
4. Weather adapter batches and caches forecast requests.
5. Pure risk functions classify checkpoints and route intervals.
6. Recommendation service compares complete, eligible routes.
7. React renders the returned routes immediately.
8. A separate corridor request loads forecast frames progressively.

### Provider feasibility gate — do this first

Proposed assessment baseline: Mapbox geocoding/directions, Open-Meteo forecasts, and MapLibre rendering. Keep adapters replaceable. Confirm credentials, allowed storage/display, attribution, geographic coverage, quotas, and hosting usage terms before locking providers; do not assume a free tier permits every deployment.

- Mapbox documents alternatives and distance/duration annotations. Alternatives depend on the journey, so three results are a feasibility test rather than a universal guarantee. Its documented profiles are automotive; do not describe them as truck-restriction-aware. [Directions documentation](https://docs.mapbox.com/api/navigation/directions/)
- Open-Meteo documents hourly wind, rain, showers, snowfall, and multi-coordinate forecast requests. Verify the selected model's variables, units, time semantics, limits, and required forecast coverage with real responses. [Forecast documentation](https://open-meteo.com/en/docs)
- MapLibre supports heatmap layers. Use that rendering capability only after defining what the visual intensity represents. [Heatmap example](https://maplibre.org/maplibre-gl-js/docs/examples/create-a-heatmap-layer/)

Spike acceptance: obtain distinct route geometries and timing metadata, normalize one weather response correctly, render it on a map, and document per-analysis request volume. If the chosen routing service cannot produce three candidates for representative journeys, evaluate a replacement or provider-supported via-point strategy before proceeding. Do not silently weaken the requirement.

## 4. Core calculations

### 4.1 Route geometry, checkpoints, and ETA

- Request full route geometry and per-segment distance/duration information.
- Establish one canonical chainage in meters. Maintain a mapping between provider segment distances and geometric interpolation distances so mismatched totals do not produce drifting checkpoint locations.
- Insert origin, checkpoints at each selected spacing, and destination. Avoid duplicate destination points on exact multiples.
- Use geodesic interpolation along the polyline, not straight-line interpolation between origin and destination.
- Build prefix sums of segment distance and duration. Interpolate elapsed time within the containing segment.
- `checkpoint_eta_utc = departure_utc + cumulative_travel_seconds`.
- Preserve route endpoints and exact distances for calculation; use simplified geometry only for rendering.
- Validate positive lengths, duration totals, coordinate order, geometry/annotation alignment, and degenerate segments.

Example: a 62-mile route sampled every 25 miles has checkpoints at 0, 25, 50, and 62 miles. Its final interval is 12 miles, not 25.

### 4.2 Weather normalization and time lookup

- Store timestamps in UTC. The form explicitly shows an editable origin timezone; reject ambiguous/nonexistent local times unless the user resolves the offset.
- Normalize wind to mph, liquid rain to inches/hour, and snowfall depth to inches/hour. For metric responses: divide km/h by 1.609344, rain mm by 25.4, and snow cm by 2.54, accounting for the provider's accumulation interval.
- If the provider separates stratiform rain and convective showers, combine their liquid amounts after verifying they are non-overlapping fields. Do not use total precipitation as rain when it includes snow.
- Use sustained wind for the supplied rules. Gusts may be displayed as context but do not silently replace the required measurement.
- For hourly accumulated precipitation, use the interval containing the checkpoint ETA, respecting whether the timestamp marks its start or end. Do not interpolate accumulated values as instantaneous rates.
- For instantaneous wind values, interpolate between bracketing observations. Do not interpolate risk categories.
- Preserve raw values, normalized values, source time, fetch time, and forecast/model metadata where available. Never manufacture an issue time the provider does not return.
- Missing required values, invalid units, or uncovered time become Unknown with a reason.

### 4.3 Risk engine

Implement pure functions without Django, network, or UI dependencies:

| Hazard | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind, mph | <25 | 25 to <35 | 35 to <45 | 45 to <55 | >=55 |
| Rain, in/hr | <0.10 | 0.10 to <0.25 | 0.25 to <0.50 | 0.50 to 1.00 inclusive | >1.00 |
| Snow, in/hr | <0.5 | 0.5 to <1.0 | 1.0 to <2.0 | 2.0 to 3.0 inclusive | >3.0 |

Apply load overrides after base classification:

- Wind >=55 mph: No Travel for every load.
- Wind >=45 and <55 mph with load >30,000 lb: No Travel.
- Wind >=35 and <45 mph with load >40,000 lb: at least Severe.
- Overall risk is the most restrictive result. Exactly 30,000 and 40,000 lb do not satisfy the respective strict greater-than conditions.

Return a stable reason code and readable explanation, e.g. `WIND_LOAD_NO_TRAVEL`: “47 mph wind with 32,000 lb exceeds the supplied load rule.” Validate nonnegative finite inputs and version the rule policy.

### 4.4 Exposure miles and recommendation

Checkpoint counts are not exposure miles. Define an explicit estimate:

1. Partition the complete route into intervals between successive checkpoints.
2. Assign each interval the maximum risk at its two endpoints. If either endpoint has missing required data, mark the interval Unknown and retain any known hazard flag separately.
3. Attribute its actual length to that category exactly once. This conservative approximation can overstate an isolated endpoint hazard; document the limitation and selected spacing.
4. Sum each category's miles; require the sum, including Unknown, to match route length within a numerical tolerance.
5. Compute average risk over complete assessed route miles. Do not rank a partially assessed route using an average over only its known section.
6. Exclude blocked/incomplete routes; sort eligible routes lexicographically by `(severe_miles, high_miles, distance_weighted_average_risk, travel_seconds)`.
7. Compare full-precision values, with only a small documented numerical tolerance for equal calculations. Round for display; stable route ID breaks a true tie.

The ranking follows the PDF's ordered priorities. It is not a weighted score that lets a faster journey override fewer Severe miles. Show the first decisive comparison, for example: “Route B has 8 fewer Severe miles; it takes 18 minutes longer.” If no route qualifies, return a null recommendation with structured reasons.

## 5. Corridor forecast and map experience

Keep two concepts visible: route colors represent weather at arrival; the heatmap represents weather across the corridor at the slider's selected time.

- Buffer the union of candidate routes by a configurable initial 25-mile radius. This width is a proposed UI default, not specified by the PDF.
- Generate a geodesically appropriate, evenly spaced corridor grid; deduplicate shared locations. Avoid a rectangular grid over an entire continental bounding box.
- Target approximately 5–10-mile grid spacing initially, adjusted to the provider model resolution. Cap at 300 grid locations for the initial implementation. If this cap requires coarsening, return and display effective resolution.
- Fetch grid forecasts independently from checkpoint forecasts so heatmap work cannot block route results. Keep exact checkpoint coordinates; coarse corridor caching must not change route risk calculations.
- Provide hourly frames from departure through departure+48h inclusive: 49 timestamps. A trip longer than 48 hours still needs arrival-time weather beyond the slider window.
- Offer Wind, Rain, Snow, and Combined risk layers, using the entered load for combined risk. Display units, legend, selected timestamp, source/freshness, and missing-data areas.
- For quantitative categories, prefer fixed-scale colored grid cells/raster shading. A blurred heatmap may provide visual context, but density accumulation must not be presented as measured mph or an exact risk category. Keep spatial sampling consistent and label interpolation.
- Load frames once, reuse map sources/layers, and update frame data locally. Slider movement must not generate a weather request per tick.
- Use WebGL point layers for checkpoints rather than hundreds of HTML markers. Reveal detailed labels on hover/focus/click.
- Keep inactive routes visible; selected route gets a clear outline. Popups show ETA, weather, category, and rule explanation. Unknown uses a distinct pattern/style.
- Desktop: compact trip form and route comparison beside the map, timeline along the bottom. Mobile: map with a collapsible results sheet and accessible controls.
- Include text labels and icons in addition to color, keyboard route selection, readable contrast, and loading/empty/error states.

## 6. API and code organization

| Endpoint | Purpose |
|---|---|
| `GET /api/places?q=...` | Debounced geocoding with resolved IDs, labels, and coordinates |
| `POST /api/route-analyses` | Validate inputs and return routes, checkpoints, exposures, ranking, warnings, and analysis ID |
| `GET /api/route-analyses/{id}/corridor` | Return corridor geometry and forecast frames, independently cached |
| `GET /api/health` | Deployment health check |

Request fields: resolved origin/destination, departure as an offset-bearing ISO timestamp, origin IANA timezone, load_lb, and spacing_miles enum. Return analysis expiry explicitly; expired corridor IDs produce an actionable response.

Response includes input echo, calculation policy version, route provider metadata, assessment timestamps, completeness, route geometry, checkpoint evidence, interval exposure, summaries, ordered eligible IDs, recommendation rationale, and typed warnings. Distinguish validation, no-route, quota, timeout, partial-weather, and forecast-horizon failures.

Suggested structure:

```text
frontend/src/
  features/trip/       # input, validation, place search
  features/routes/     # summaries, comparison, explanations
  features/map/        # route/checkpoint/corridor layers and slider
  api/                 # typed client and query definitions
backend/
  config/
  routing/providers/   # directions and geocoding adapters
  weather/providers/   # forecast adapter and normalization
  analysis/            # geometry, ETA, risk, exposure, ranking
  api/                 # serializers, views, error contract
  tests/fixtures/
docs/
  architecture.md
  assumptions.md
  walkthrough.md
```

Maintain a checked-in OpenAPI schema or generated TypeScript types so backend and frontend agree on units, timestamps, categories, and nullable fields.

## 7. Reliability, performance, and operations

- Keep provider secrets on the server. Restrict any necessary public basemap token by origin and scope; commit an `.env.example` without real credentials.
- Use bounded provider concurrency, request deadlines, and limited retries with backoff for transient errors; honor provider retry guidance. Do not retry invalid inputs.
- Cache weather by exact/canonical provider location, variables, units, forecast window, and freshness policy. Cache raw forecasts independently from load-dependent classification.
- Include departure, load, spacing, route geometry/version, forecast identity, and rule version in calculated-analysis keys. A load change must not reuse stale risk results.
- Start with short configurable forecast freshness (for example 15 minutes), verified against provider update behavior. Never silently serve stale forecasts as current.
- Debounce place search, cancel obsolete frontend requests, and prevent late responses from replacing a newer trip.
- Bound trip size and corridor requests using limits measured during the spike. Return clear validation rather than silently changing checkpoint spacing.
- Log request IDs, provider latency/errors, cache hits, location counts, payload size, and analysis duration without secrets or unnecessary full addresses.
- Validate Django production settings, HTTPS, allowed hosts/origins, input limits, request throttling, and an origin-aware API access policy. Do not treat CORS as authorization.

Provisional targets to validate on a documented representative 1,000-mile journey with 10-mile checkpoints and three routes: cached route analysis p95 <=2 seconds; cold route analysis p95 <=10 seconds; cached slider frame update <=100 ms; responsive map interaction around 50+ fps on a stated reference desktop. These are engineering targets, not promises independent of provider latency. Record cold/warm runs and corridor completion separately. If profiling proves synchronous analysis cannot fit host deadlines, add a background job and polling using the same analysis contract; do not add a queue preemptively.

## 8. Verification and acceptance

Tests should prove business behavior and failure handling, not merely mirror functions.

| Area | Required evidence |
|---|---|
| Thresholds | Below/at/above 25,35,45,55 mph; 0.10,0.25,0.50,1.00 rain; 0.5,1,2,3 snow; fractional wind |
| Load overrides | 30,000/30,001 and 40,000/40,001 lb at relevant wind bands; 55 mph always blocked |
| Weather | Metric conversions; rain/showers semantics; snowfall depth; hourly interval boundaries; null values; uncovered forecasts |
| Time | UTC offsets, origin/browser timezone mismatch, DST gaps/repeated hours, ETA crossing midnight |
| Geometry | Curved route, exact spacing multiple, short trip, zero-length segment, partial last interval, metadata mismatch |
| Exposure | Category miles sum to total; distance-weighted average; Unknown stays separate; conservative endpoint policy |
| Ranking | Fewer Severe miles beats shorter duration; next tie-breaks follow order; blocked/unknown routes excluded; all blocked yields no recommendation |
| Integrations | Recorded deterministic provider fixtures; malformed response, timeout, 429, fewer routes, missing variables |
| UI | Submit/select/inspect routes; spacing/load/departure changes; all five risk labels; incomplete data; 0h and 48h frames; slider does not alter recommendation |
| Performance | Cold/warm benchmark, request counts, browser network trace during slider scrubbing, mobile map interaction |
| Deployment | Public URL works from clean browser; no exposed secrets; real provider smoke test; health endpoint and error logging |

Use a fixed-clock, clearly labeled fixture mode for repeatable screenshots and the walkthrough. Keep a separate live-data smoke test; do not present recorded weather as current. Real forecasts may contain no severe weather, so fixture scenarios are necessary to demonstrate every rule reliably.

## 9. Delivery sequence

Estimate: 10 focused engineering days for one experienced full-stack engineer, plus 1–2 days contingency for provider/hosting issues. Assumes credentials and account access are available. This is an estimate, not a supplied deadline.

| Phase | Time | Work and exit criterion |
|---|---|---|
| 0. Feasibility and policy | Day 1 | Confirm provider capabilities/terms, three-route demo journeys, forecast semantics and call budget. Record assumptions and sample fixtures. |
| 1. Foundation and vertical slice | Day 2 | React/Django skeleton, typed contract, CI, one live route with one arrival-time forecast rendered on map. Deploy an early skeleton. |
| 2. Correct analysis | Days 3–4 | Three-route integration, checkpoint geometry/ETAs, normalization, risk/load rules, interval exposures, exact ranking. Domain acceptance tests pass. |
| 3. Driver workflow | Days 5–6 | Full form, search, route comparison, all map layers, checkpoint details, explainable recommendations, failure states, mobile layout. Complete route-analysis journey works. |
| 4. Forecast corridor | Days 7–8 | Grid, batching/cache, independent loading, 49 forecast frames, smooth slider, clear legends, bounded resolution. Performance evidence recorded. |
| 5. Hardening and submission | Days 9–10 | Browser/integration checks, production settings, deployment smoke test, README, architecture/assumptions, Loom recording and repository cleanup. |

If time becomes constrained, remove optional layer toggles and animation first. Preserve all required routes, arrival-time sampling, load rules, ranking, corridor forecast, and slider. Do not trade correctness for additional features.

## 10. Submission checklist and walkthrough

Repository: reproducible setup, dependency lockfiles, environment example, test commands, architecture/data-flow explanation, precise risk policy, provider attribution, limitations, deployment instructions, and hosted/Loom links. CI runs domain tests, frontend checks/build, and a deterministic browser smoke journey.

Hosted application: real integrations work, a labeled demo scenario is available, no account is required for evaluation, loading/errors are clear, and provider outages do not produce fabricated safe results.

Suggested 7–8 minute Loom:

1. Explain the driver problem and enter a journey (45 seconds).
2. Compare three routes and explain the ranking (90 seconds).
3. Inspect checkpoint ETA/weather and change load to trigger a rule (90 seconds).
4. Scrub the corridor slider and explain its distinct timestamp (90 seconds).
5. Show all-blocked, missing-data, or fewer-alternatives behavior using labeled fixtures (45 seconds).
6. Show architecture, decisive tests, performance results, and known limitations (90 seconds).

Definition of done: every PDF requirement is demonstrated by an acceptance check, all three deliverables are accessible, assumptions are visible, and the recommendation can be reproduced from returned checkpoint evidence and the documented rule policy.
