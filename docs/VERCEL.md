# Deploy Spotter on Vercel

## What caused the JSON parsing error

The frontend calls `/api/...` on its own origin. Vite proxies these calls to Django only during `npm run dev`. Uploading `dist` as a Vite-only deployment does not deploy the Python API. A missing API endpoint can then return Vercel's plain-text 404 (`The page could not be found`), which cannot be parsed as JSON.

On 28 October 2026, `https://truckrouteplanner.vercel.app/api/health` returned HTTP 404 with `Content-Type: text/plain`. This confirms that the API health endpoint was not reachable on that deployment.

The frontend API helper now checks status/content type before parsing and reports an actionable deployment error instead of `Unexpected token 'T'`.

## Deployment architecture

This repository now selects Vercel's **Django** framework explicitly in `vercel.json`. Vercel discovers the root `manage.py` and `backend.wsgi.application`. The build command installs the frontend dependencies and builds React into `dist`. Django serves `dist/index.html`; Vercel collects Django's configured static files and serves `/assets/` through its CDN. Requests to `/api/...` reach Django on the same domain. A separate frontend service and CORS setup are unnecessary for this arrangement.

See the [official Django deployment guide](https://vercel.com/docs/frameworks/full-stack/django). If using the Vercel CLI, use a current release supporting native Django (the documented minimum is 50.38.0).

## 1. No Redis or database required

The frontend sends a signed, compressed trip token in the corridor POST request body. It contains the departure, load, mode, and compact corridor geometry, and expires after 15 minutes. Any Vercel instance can verify it with the same `DJANGO_SECRET_KEY` and compute the forecast without retrieving an analysis from another instance's memory.

The token is signed, not encrypted; it carries trip information the browser already received and never contains provider credentials. It is sent in a request body rather than the URL. Only the coarse weather-corridor geometry is compacted; route geometry, checkpoint arrival times, and recommendation calculations are unchanged.

Process-local caching is now an optional speed optimization. A cold cache or another server instance does not break the trip workflow. `REDIS_URL` remains optional for shared caching if you choose to add it later. You do not need Redis, a relational database, or migrations for this deployment.

## 2. Set Vercel environment variables

In **Project → Settings → Environment Variables**, add these for Production and Preview:

| Name | Value |
|---|---|
| `DJANGO_SECRET_KEY` | A newly generated long random secret |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `truckrouteplanner.vercel.app` plus any custom domain, comma-separated; no `https://` |

Vercel's exposed `VERCEL_URL` and `VERCEL_PROJECT_PRODUCTION_URL` are also added to allowed hosts automatically. Make sure system environment variables are exposed if relying on automatic preview host support. An explicit allowed-host list can include the exact preview hostname instead.

Optional: `MAPBOX_TOKEN` for Mapbox routing, `ROUTING_BASE_URL` for a production OSRM service, and optionally `REDIS_URL`/`CACHE_KEY_PREFIX` if you later want shared caching. Leave `REDIS_URL` unset when not using Redis.

Generate a secret locally with:

```text
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste its output into Vercel's environment-variable field, not into the source repository.

## 3. Correct the existing project settings

Under **Project → Settings → Build and Deployment**:

- Root Directory: repository root (where `manage.py`, `package.json`, and `vercel.json` live).
- Framework Preset: **Django**. The checked-in `framework: "django"` selects this instead of Vite.
- Build Command: use the checked-in `npm ci && npm run build`; clear conflicting dashboard overrides.
- Install Command: leave the framework default so Python dependencies are installed from `requirements.txt`.
- Output Directory: **clear the `dist` override** and use the framework default. This is a Django deployment, not a static-only export.
- Remove any old catch-all rewrite to `/index.html` that intercepts `/api` requests. This setup uses Django's URL routing.

The Python version is set to 3.12 in `.python-version`. `vercel.json` configures the WSGI function for up to 60 seconds and excludes development dependencies/test artifacts from its bundle. Vercel runs `collectstatic` automatically for Django; the frontend build must finish before static collection.

## 4. Deploy the updated commit

Commit and push the new source/configuration to the branch Vercel deploys, then deploy that latest commit after adding environment variables. Redeploying an old commit will not include the fix. If changing configuration on an existing project, consider a clean redeploy without the old build cache.

## 5. Verify the backend before trying the form

Open:

```text
https://truckrouteplanner.vercel.app/api/health
```

Expected: HTTP 200, JSON content type, and `{"status":"ok","version":"1.0.0"}`. This health route intentionally avoids Redis so you can distinguish API deployment from cache connectivity.

Then open the home page and run the demo. Verify three route cards and the corridor forecast. The demo analysis returns the signed token and the frontend sends it with the corridor request; this second check verifies the complete flow. Finally test a live public-city journey.

Troubleshooting:

- **Plain-text 404 at `/api/health`:** the deployed commit/framework/routing still does not expose Django.
- **Django `DisallowedHost`:** add the actual host to `DJANGO_ALLOWED_HOSTS` or expose Vercel's system hostname variables, then redeploy.
- **Build error naming `DJANGO_SECRET_KEY`:** set the missing server environment variable for the relevant deployment environment.
- **You previously set an unusable `REDIS_URL`:** remove it and redeploy. The default deployment needs no Redis service.
- **Invalid/expired trip token:** analyze the trip again. Keep `DJANGO_SECRET_KEY` stable across instances; rotating it invalidates existing tokens.
- **Function timeout:** inspect provider latency and Vercel function logs. Larger live trips can require more time than a particular plan permits; the supplied duration is a configuration request, not a latency guarantee.

Local builds, API tests, and configuration tests can validate the repository changes. An actual Vercel deployment still needs a production smoke test after your Django environment variables are configured.
