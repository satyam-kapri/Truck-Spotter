# Walkthrough script (5–10 minutes)

1. **0:00–0:45 — Purpose.** Open Spotter. Point out the demo badge and explain that fixtures make the assessment repeatable. Identify origin, destination, local departure, load, and checkpoint spacing.
2. **0:45–2:00 — Compare.** Analyze the trip and inspect all three corridors. Explain the recommendation: Severe miles, High miles, distance-weighted risk, then travel time. A slightly slower route can rank higher.
3. **2:00–3:15 — Inspect.** Click a checkpoint. Show mile, ETA, weather units, category, and reasons. Change spacing from 25 to 10 miles and recompute.
4. **3:15–4:15 — Load rules.** Use a demo departure that exposes the Indianapolis corridor to stronger winds, increase load above 30,000 or 40,000 lb, and show the resulting rule. Explain strict boundaries and No Travel exclusion.
5. **4:15–5:30 — Forecast corridor.** Scrub from departure to +48 hours, use play/pause, change layer, and toggle weather visibility. Explain that route colors use arrival weather while the corridor is a time snapshot.
6. **5:30–6:30 — Live integrations.** Switch to live mode, resolve public cities, and submit. Explain real provider responses, possible fewer alternatives, and honest errors. Never describe fixture weather as current.
7. **6:30–8:00 — Engineering.** Show the pure domain engine, decisive tests, backend-owned rules, interval accounting, time normalization, separately cached corridor frames, and Docker/CI configuration. Explain public-provider limits and why shared Redis is needed before horizontal scaling.

Before recording, run the tests/build, verify network access, and choose a clear synthetic scenario. Add the actual hosted URL, GitHub URL, and Loom URL to README only after each is available.
