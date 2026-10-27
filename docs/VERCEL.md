# Deploy Spotter on Vercel

## What caused the JSON parsing error

The frontend calls `/api/...` on its own origin. Vite proxies these calls to Django only during `npm run dev`. Uploading `dist` as a Vite-only deployment does not deploy the Python API. A missing API endpoint can then return Vercel's plain-text 404 (`The page could not be found`), which cannot be parsed as JSON.

On 28 October 2026, `https://truckrouteplanner.vercel.app/api/health` returned HTTP 404 with `Content-Type: text/plain`. This confirms that the API health endpoint was not reachable on that deployment.

The frontend API helper now checks status/content type before parsing and reports an actionable deployment error instead of `Unexpected token 'T'`.

## Deployment architecture

This repository now selects Vercel's **Django** framework explicitly in `vercel.json`. Vercel discovers the root `manage.py` and `backend.wsgi.application`. The build command installs the frontend dependencies and builds React into `dist`. Django serves `dist/index.html`; Vercel collects Django's configured static files and serves `/assets/` through its CDN. Requests to `/api/...` reach Django on the same domain. A separate frontend service and CORS setup are unnecessary for this arrangement.

See the [official Django deployment guide](https://vercel.com/docs/frameworks/full-stack/django). If using the Vercel CLI, use a current release supporting native Django (the documented minimum is 50.38.0).

## 1. Configure shared Redis

Provision a managed Redis database, such as through Vercel Marketplace, and copy its **TCP connection string**. Set it as `REDIS_URL`. It must begin with `redis://` or `rediss://`; an HTTPS REST endpoint and REST token are not interchangeable with that URL.

The analysis response and the subsequent corridor request may run on different Vercel instances. A process-local cache cannot reliably share the analysis ID between them. Django uses its Redis cache backend when `REDIS_URL` is set. A Vercel deployment without this setting fails early with a clear configuration error rather than deploying an intermittently broken corridor.

Keep the Redis URL/password in server environment variables. Do not add a `VITE_` prefix or put it in Git. This project does not require a relational database or migrations.

## 2. Set Vercel environment variables

In **Project → Settings → Environment Variables**, add these for Production and Preview:

| Name | Value |
|---|---|
| `DJANGO_SECRET_KEY` | A newly generated long random secret |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `truckrouteplanner.vercel.app` plus any custom domain, comma-separated; no `https://` |
| `REDIS_URL` | Your private managed Redis TCP/TLS connection string |

Vercel's exposed `VERCEL_URL` and `VERCEL_PROJECT_PRODUCTION_URL` are also added to allowed hosts automatically. Make sure system environment variables are exposed if relying on automatic preview host support. An explicit allowed-host list can include the exact preview hostname instead.

Optional: `MAPBOX_TOKEN` for Mapbox routing, `ROUTING_BASE_URL` for a production OSRM service, and `CACHE_KEY_PREFIX` to separate cache namespaces if sharing Redis across projects.

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

Then open the home page and run the demo. Verify three route cards and the corridor forecast. The demo analysis and corridor still use shared Redis, so this second check verifies more than the health endpoint alone. Finally test a live public-city journey.

Troubleshooting:

- **Plain-text 404 at `/api/health`:** the deployed commit/framework/routing still does not expose Django.
- **Django `DisallowedHost`:** add the actual host to `DJANGO_ALLOWED_HOSTS` or expose Vercel's system hostname variables, then redeploy.
- **Build error naming `DJANGO_SECRET_KEY` or `REDIS_URL`:** set the missing server environment variable for the relevant deployment environment.
- **Health succeeds but analysis fails with Redis errors:** check the TCP URL, credentials, provider network/TLS requirements, and runtime logs. Do not disable TLS verification.
- **Function timeout:** inspect provider latency and Vercel function logs. Larger live trips can require more time than a particular plan permits; the supplied duration is a configuration request, not a latency guarantee.

Local builds, API tests, and configuration tests can validate the repository changes. An actual Vercel deployment and managed Redis connection still need a production smoke test after your environment variables are configured.
