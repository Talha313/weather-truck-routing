# Weather-Aware Truck Routing

A React + Django app that helps a truck driver pick the **safest route** based on **weather, load weight and travel time**.

Enter an origin, destination, departure time and load weight. The app then:

1. gets **3 truck route options** from a routing API,
2. places **weather checkpoints every 10 / 25 / 50 miles** and works out the truck's **ETA at each one**,
3. reads the **hourly forecast at that ETA** and classifies risk with the assessment's **risk table and load rules**,
4. **recommends** a route (fewest Severe miles → fewest High miles → lowest average risk → shortest travel time) and explains why, and
5. draws the routes, risk-coloured checkpoints, ETAs and summaries on a map, plus a **corridor weather heatmap with a 0–48 h forecast slider**.

| Layer | Stack |
|---|---|
| Backend | Python 3.11, Django 5.2, Django REST Framework. Stateless: no database. |
| Frontend | React 18, TypeScript (strict), Vite, Tailwind CSS, Leaflet / react-leaflet |
| Routing | [Valhalla](https://valhalla.github.io/valhalla/) `truck` costing (FOSSGIS public server), with [OSRM](https://project-osrm.org/) as fallback |
| Weather | [Open-Meteo](https://open-meteo.com/) hourly forecast (no API key) |
| Geocoding | [Photon](https://photon.komoot.io/) (OpenStreetMap data, allows search-as-you-type) |
| Basemap | Esri World Light Gray Canvas |

None of these services need an API key, so the project runs right after cloning.

---

## Running locally

**Backend** (http://localhost:8000):

```bash
cd backend
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py runserver
```

**Frontend** (http://localhost:5173), in a second terminal:

```bash
cd frontend
npm install
cp .env.example .env        # VITE_API_URL=http://localhost:8000
npm run dev
```

Open the app and click one of the example trips (*Chicago → Dallas*, *Denver → Salt Lake City*, *Seattle → Boise*), or type your own places.

**Tests:**

```bash
cd backend && ./venv/bin/python manage.py test routing   # 39 unit tests
cd frontend && npm run typecheck && npm run build
```

---

## How it works

```
React ──POST /api/plan/────▶ geocode ─▶ 3 truck routes ─▶ checkpoints + ETAs ─▶ forecasts at ETAs ─▶ risk ─▶ ranking
      ◀── routes, checkpoints, recommendation (≈5–10 s)
React ──POST /api/heatmap/─▶ same routes (cached) ─▶ corridor grid ─▶ forecasts 0–48 h ─▶ risk score per cell per hour
      ◀── grid + 49 hourly frames (≈50–60 KB)
```

The heatmap is a separate request. That way the routes appear first, and the ~250 extra forecasts load while the user reads the results.

### 1. Routes: `backend/routing/services/routing.py`
- **Valhalla `truck` costing** honours truck restrictions and truck speeds. The vehicle weight it receives is the load plus 35,000 lb for an empty tractor-trailer.
- Routing engines return *up to* N alternatives and often fewer. Any missing options are filled by asking the same engine for a route **forced through a detour point** on either side of the straight line between origin and destination. A candidate is accepted only if it is genuinely different (less than 85% overlap with existing routes) and no more than 60% longer than the shortest route.
- If Valhalla is down, the same logic runs on OSRM, with speeds capped at 65 mph.

### 2. Checkpoints and ETAs: `planner.py`, `hos.py`
- Checkpoints sit at mile 0, every *N* miles, and at the destination. The driving time to each comes from the routing engine's own timing along the route.
- **Hours-of-Service breaks** are on by default and can be switched off. They insert a 30-min break after 8 h and a 10-h rest after 11 h of driving, so later checkpoints are matched with the weather the truck will really meet.
- Each checkpoint **represents the route miles closer to it than to its neighbours** (it covers half the gap on each side). These are the miles counted as "Severe miles", "High miles" and so on.

### 3. Weather at the ETA: `weather.py`
- One Open-Meteo request per 100 locations, run in parallel and cached for 30 min. Checkpoints are snapped to a 0.05° grid so overlapping routes share forecasts.
- Values are read with Open-Meteo's semantics in mind. **Wind** is instantaneous, so it is interpolated between hours. **Rain/snow** totals cover the *preceding* hour, so the value used is the one for the hour the truck is in, which is directly in in/hr.
- Rain = `rain + showers` (liquid); snow = `snowfall` (in/hr); wind = sustained 10 m wind in mph. Gusts are shown but not scored, because the table gives one wind threshold.

### 4. Risk rules: `risk.py` (fully unit-tested)

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | < 25 | 25 – < 35 | 35 – < 45 | 45 – < 55 | **≥ 55** |
| Rain (in/hr) | < 0.10 | 0.10 – < 0.25 | 0.25 – < 0.50 | 0.50 – 1.00 | **> 1.00** |
| Snow (in/hr) | < 0.5 | 0.5 – < 1.0 | 1.0 – < 2.0 | 2.0 – 3.0 | **> 3.0** |

The PDF's ranges share their endpoints, so each band includes its lower edge, except where the table says otherwise (">1.00", ">3.0", "≥55").

Load rules are applied on top of the wind level:
- ≥ 55 mph → No Travel for any load
- 45–54 mph with **> 30,000 lb** → No Travel
- 35–44 mph with **> 40,000 lb** → Severe

A checkpoint's level is the **worst** of wind, rain and snow. The popup says which hazard decided it and whether a load rule applied.

### 5. Recommendation: `recommend.py`
Routes are sorted strictly by the spec's order: **Severe miles → High miles → average risk (mile-weighted, 0–4) → travel time**.
- **No Travel miles rank before all of these.** The spec doesn't mention them, but they are clearly worse than Severe. If every route has No Travel miles, the app shows a warning suggesting a later departure.
- Miles are compared to 0.1 mi and average risk to 0.01, so rounding noise never decides a ranking.
- Each runner-up gets a one-line reason, e.g. *"25 fewer High miles than Route C (0.0 vs 25 mi)."*

### 6. Map and heatmap: `frontend/src/lib/heatRaster.ts`, `components/HeatmapLayer.tsx`
- The backend builds a grid of cells within about 35 mi of any route. Cell size grows with trip length so a request never needs more than 260 forecasts. Each cell gets a **continuous 0–4 risk score** per hour: the whole number is the discrete level (load rules included), the fraction shows how far into that band the weather is.
- The frontend paints the field into a small canvas. It blends **in time** between hourly frames, so playback is smooth rather than jumping each hour, and **in space** between grid cells. Cells outside the corridor fade to transparent at the edge. Rows are laid out in Web Mercator so the image lines up with the map.
- The canvas sits inside a Leaflet overlay, so moving the slider is a plain canvas redraw (a few ms) with no image reloads or flicker.
- The slider (0–48 h in 15-min steps, with play/pause) also moves **a truck marker on each route** to where it would be at that time and shows the selected truck's status (*driving at mile 312*, *on a required break*, *arrived*).
- Routes, checkpoints and markers are memoised React components, so moving the slider re-renders only the trucks and the heatmap.

---

## API

| Method | Path | Body / query | Returns |
|---|---|---|---|
| GET | `/api/health/` | | `{status}` |
| GET | `/api/geocode/?q=` | text | `{results: [{label, lat, lon}]}` |
| POST | `/api/plan/` | `origin`, `destination` (text or `{label, lat, lon}`), `departure_time` (ISO 8601), `load_weight_lbs` (0–120,000), `checkpoint_interval_miles` (10/25/50), `include_hos` | routes, checkpoints (ETA, weather, risk), risk miles, recommendation |
| POST | `/api/heatmap/` | `origin`, `destination`, `departure_time`, `load_weight_lbs` | grid + 49 hourly risk frames |

Validation errors return 400 with field messages. Failures of the routing, weather or geocoding services return 502 with a readable message.

---

## Deployment

**Backend (Render):** `render.yaml` is a Render Blueprint. After the first deploy, set `CORS_ALLOWED_ORIGINS` to the frontend URL. Any host that runs gunicorn works (`Procfile` included). Environment variables are listed in `backend/.env.example`.

**Backend (PythonAnywhere):** manual-config web app with Python 3.11, source `backend/`, settings module `config.settings`. Put the settings in `backend/.env` (it is read on startup). No database or static files, so skip `migrate` and `collectstatic`. Free accounts can only reach allow-listed hosts: Valhalla is blocked, so routing falls back to OSRM (car profile, load weight still applies to risk). All free accounts share outbound IPs, which share Open-Meteo's per-IP limit, so set `HEATMAP_MAX_CELLS=100` and `WEATHER_CACHE_TTL_S=10800` to cut weather requests per trip by about half.

**Frontend (Vercel / Netlify):** root `frontend`, build `npm run build`, output `dist`, environment variable `VITE_API_URL=https://<your-api-host>`.

---

## Assumptions and limits
- **US units throughout** (miles, mph, inches, lb, °F). Routing works anywhere Valhalla/OSRM have coverage, but the risk table is in US units.
- **Departure** must be from 6 h ago up to 7 days ahead; beyond that, forecasts are not reliable enough to route on.
- **ETAs use the routing engine's truck timings** plus the optional HOS stops. Traffic, loading time and the 70-hour/8-day limit (which needs the driver's history) are not modelled.
- **Wind direction (crosswind) and gusts** are not scored, because the provided table uses one wind speed.
- The free public services (Valhalla FOSSGIS, OSRM demo, Open-Meteo free tier) have fair-use rate limits. In production you would point the `*_URL` settings at paid or self-hosted instances. Caching keeps repeat requests cheap.

## Project layout

```
backend/
  config/                 Django settings & URLs (env-driven)
  routing/
    services/
      routing.py          Valhalla/OSRM, guaranteed 3 alternatives
      planner.py          checkpoints, ETAs, risk miles, response
      weather.py          Open-Meteo batching, caching, ETA lookup
      risk.py             threshold table + load rules
      recommend.py        ranking + explanations
      heatmap.py          corridor grid, 0–48 h frames
      hos.py              Hours-of-Service timing
      geocoding.py        Photon search
      geo.py              haversine, polyline decoding, simplification
    tests/                39 unit tests (rules, ranking, timing, geometry)
    views.py, serializers.py, urls.py
frontend/src/
  App.tsx                 state, data flow, layout
  components/             TripForm, PlaceInput, RouteCard, Recommendation,
                          MapView, RouteLayers, HeatmapLayer, TimeSlider, …
  lib/                    api client, heatmap renderer, risk colours, HOS inverse, geo
```
