# Verification record — 27 October 2026

## Completed

- TypeScript check and Vite production build pass.
- Django system check passes.
- All 49 domain/API/provider tests pass. Coverage includes thresholds, strict load overrides, geometry/ETA, exposure accounting, ranking, missing data, time/units, provider failures, via-point candidates, complete demo analysis, and 49-frame corridor responses.
- npm dependency audit after upgrading MapLibre: zero reported vulnerabilities.
- Real OSRM and Open-Meteo API calls returned successful responses for the public Chicago–Nashville example.
- Full live backend analysis before the via-point enhancement completed in 2.66 seconds with two complete candidates. A subsequent real routing smoke test verified three candidates: approximately 468, 438, and 472 miles, with the third explicitly generated through a provider-computed via point.
- A single local demo benchmark at 10-mile spacing assessed 170 checkpoints across three routes in 84 ms. Corridor generation produced 53 locations × 49 frames in 30 ms. These are individual local observations, not p95 guarantees or live-provider performance claims.
- Browser verification: desktop map renders, live analysis and live corridor complete, selected routes draw on the actual road geometry, forecast slider reaches +48h, weather layer switches, and increasing load to 45,001 lb changes the exposed demo route to No Travel.
- Responsive inspection at 390×844: trip and map tabs, map, and forecast controls remain usable. Temporary viewport override was reset.
- Local Git repository created and application source committed.
- Review screenshot saved at `output/spotter-preview.png`; local preview left on a complete, labeled demo.

## Checkpoint interaction update — 28 October 2026

- Production build and TypeScript check pass after the interaction fix.
- Verified that selecting checkpoint 6 from Inspect checkpoints opens its risk details, highlights the corresponding list row, centers the map, and displays a numbered marker with the same checkpoint label.
- Closed the details and clicked the checkpoint directly on the map; its details reopened and remained open. A unified map click handler prioritizes checkpoint hits over the route underneath.
- Verified the same list-to-map interaction at 390×844. The map tab opens automatically and the marker remains visible above the details panel. Restored the normal viewport afterward.
- Review screenshot: `output/spotter-checkpoint-selection.png`.

## Limits and remaining external deliverables

Vercel configuration update (28 October 2026): the public `/api/health` returned HTTP 404 and plain text, confirming the reported non-JSON API response. Added native Django Vercel configuration, shared Redis cache settings, deployment documentation, and actionable frontend API errors. All 55 backend tests and 6 frontend API tests pass, and the production frontend build succeeds. A live Vercel redeploy with server environment variables and Redis remains to be verified; local checks do not confirm a hosted deployment.

- No authenticated GitHub remote or container hosting destination is configured. The repository is local; a public hosted URL has not been created.
- Dockerfile is supplied, but the installed Docker client cannot reach a running Docker engine, so a container image build has not been verified here.
- Loom recording access is unavailable; the recording script is supplied in `docs/WALKTHROUGH.md`.
- Live provider quotas and hosting terms must fit the eventual deployment. The default public OSRM/Photon endpoints are demonstration services.
- A later live browser request encountered an intermittent external-provider error; the UI displayed the error and retained the clearly labeled previous demo rather than fabricating live results. Successful live analysis and corridor rendering were verified earlier in the same session.
- A p95 load test and a measured FPS benchmark have not been run. Vite reports a large map-library bundle; map code and worker assets are served separately, and forecast scrubbing reuses loaded frames.
