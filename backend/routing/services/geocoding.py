"""Place search via Photon (komoot), an OSM geocoder that explicitly allows search-as-you-type."""

import hashlib

from django.conf import settings
from django.core.cache import cache

from .http import UpstreamError, session

# Places a truck route can start or end at, not rivers, forests, etc.
USEFUL_KEYS = {"place", "highway", "building", "amenity", "shop", "industrial", "landuse", "aeroway", "office"}


def _label(props: dict) -> str:
    name = props.get("name") or props.get("street") or ""
    if props.get("housenumber") and props.get("street"):
        name = f"{props['housenumber']} {props['street']}"
    parts = [name, props.get("city") if props.get("city") != name else None, props.get("state"), props.get("countrycode")]
    return ", ".join(p for p in parts if p)


def search(query: str, limit: int = 6) -> list[dict]:
    query = query.strip()
    if len(query) < 2:
        return []
    key = "geo:" + hashlib.sha1(f"{limit}:{query.lower()}".encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        resp = session.get(settings.PHOTON_URL, params={"q": query, "limit": limit * 2, "lang": "en"}, timeout=10)
        resp.raise_for_status()
        features = resp.json().get("features", [])
    except Exception as exc:
        raise UpstreamError(f"Geocoding service unavailable: {exc}") from exc

    results, seen = [], set()
    for feat in features:
        props = feat.get("properties", {})
        if props.get("osm_key") not in USEFUL_KEYS:
            continue
        label = _label(props)
        if not label or label in seen:
            continue
        seen.add(label)
        lon, lat = feat["geometry"]["coordinates"]
        results.append({"label": label, "lat": round(lat, 6), "lon": round(lon, 6)})
        if len(results) == limit:
            break
    cache.set(key, results, 24 * 60 * 60)
    return results


def resolve(place: dict | str) -> dict:
    """Accept {label, lat, lon} (from autocomplete) or free text, return {label, lat, lon}."""
    if isinstance(place, dict) and place.get("lat") is not None and place.get("lon") is not None:
        return {"label": place.get("label") or f"{place['lat']:.4f}, {place['lon']:.4f}",
                "lat": float(place["lat"]), "lon": float(place["lon"])}
    text = place.get("label", "") if isinstance(place, dict) else place
    matches = search(text, limit=1)
    if not matches:
        raise LookupError(f"Could not find a location for “{text}”.")
    return matches[0]
