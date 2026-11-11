"""Builds the places database from data/starter_places.json.

Step 1  python -m scripts.seed_places --geocode [--wiki]
        Looks each place up on OpenStreetMap (Nominatim, 1 request per 1.1 s, about 2 minutes for 87 places)
        and writes data/places_geocoded.json. Safe to stop and re-run: finished places are skipped.
        Places that could not be found, or that landed outside Pakistan, are flagged in the report.
        --wiki also adds a Wikipedia thumbnail and a source link where a matching article exists.

Photos  python -m scripts.seed_places --photos
        For places that already have coordinates and no photo: tries the Wikipedia article (by title, then by
        search) and then freely licensed photos on Wikimedia Commons. Safe to re-run.

Step 2  python -m scripts.seed_places --import [--overwrite] [--dry-run]
        Validates and writes the places to MongoDB. Existing places are left alone unless --overwrite is given,
        so admin edits are not lost.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.models.place import PlaceCreate
from app.services import places as places_svc
from app.services.geocode import URL as NOMINATIM_URL

DATA = Path(__file__).resolve().parent.parent / "data"
SRC, OUT = DATA / "starter_places.json", DATA / "places_geocoded.json"
PK_BOX = (23.5, 37.2, 60.8, 77.9)  # lat_min, lat_max, lng_min, lng_max
GAP = 1.1  # Nominatim's usage policy allows at most 1 request per second


def in_pakistan(lat: float, lng: float) -> bool:
    return PK_BOX[0] <= lat <= PK_BOX[1] and PK_BOX[2] <= lng <= PK_BOX[3]


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save(rows: list[dict]) -> None:
    OUT.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _nominatim(http: httpx.Client, settings: Settings, query: str) -> dict | None:
    r = http.get(
        NOMINATIM_URL,
        params={"q": query, "format": "jsonv2", "limit": 1, "countrycodes": settings.geocode_country_codes},
    )
    r.raise_for_status()
    time.sleep(GAP)
    hits = r.json()
    return hits[0] if hits else None


def _wikipedia_coordinates(http: httpx.Client, row: dict) -> tuple[float, float, str] | None:
    """Notable places have coordinates on their Wikipedia article, which finds many that OpenStreetMap search misses."""
    for query in (row.get("wiki") or row["name"], f"{row['name']} {row['destination']}", f"{row['name']} Pakistan"):
        r = http.get(WIKI_API, params={"action": "opensearch", "search": query, "limit": 1, "namespace": 0, "format": "json"})
        time.sleep(0.3)
        data = r.json() if r.status_code == 200 else []
        title = data[1][0] if len(data) > 1 and data[1] else None
        if not title or not same_subject(title, row["name"]):
            continue
        r = http.get(WIKI_API, params={"action": "query", "prop": "coordinates", "titles": title, "format": "json"})
        time.sleep(0.3)
        pages = ((r.json().get("query") or {}).get("pages") or {}).values() if r.status_code == 200 else []
        for page in pages:
            coords = page.get("coordinates") or []
            if coords:
                return float(coords[0]["lat"]), float(coords[0]["lon"]), f"Wikipedia: {title}"
    return None


def find_coordinates(http: httpx.Client, settings: Settings, place: dict, row: dict) -> None:
    """Tries the exact query, then the name with its destination, then the Wikipedia article's coordinates."""
    attempts = [place["query"], f"{place['name']}, {place['destination']}, Pakistan", f"{place['name']}, Pakistan"]
    try:
        for query in dict.fromkeys(attempts):
            hit = _nominatim(http, settings, query)
            if hit:
                lat, lng = float(hit["lat"]), float(hit["lon"])
                row.update(lat=round(lat, 5), lng=round(lng, 5), matched=hit.get("display_name", ""))
                row["status"] = "ok" if in_pakistan(lat, lng) else "review"
                return
        found = _wikipedia_coordinates(http, row)
        if found:
            lat, lng, label = found
            row.update(lat=round(lat, 5), lng=round(lng, 5), matched=label)
            row["status"] = "ok" if in_pakistan(lat, lng) else "review"
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        row["error"] = str(exc)[:120]


def geocode(settings: Settings, wiki: bool) -> int:
    if not settings.nominatim_contact_email:
        print("Set NOMINATIM_CONTACT_EMAIL in .env first. Nominatim requires a contact address.")
        return 1
    headers = {"User-Agent": settings.user_agent}
    done = {r["query"]: r for r in load(OUT)}
    rows = []
    with httpx.Client(headers=headers, timeout=20, follow_redirects=True) as http:
        for i, place in enumerate(load(SRC), 1):
            prev = done.get(place["query"])
            if prev and prev.get("status") in ("ok", "review") and (not wiki or prev.get("wiki_done")):
                rows.append(prev)
                continue
            row = {**place, "status": "missing", "wiki_done": False}
            find_coordinates(http, settings, place, row)
            time.sleep(GAP)
            if wiki and row["status"] != "missing":
                add_wikipedia(http, row)
            print(f"[{i:>3}] {row['status']:<7} {place['name']}")
            rows.append(row)
            save(rows + [d for q, d in done.items() if q not in {x['query'] for x in rows}])
    save(rows)
    bad = [r for r in rows if r["status"] != "ok"]
    print(f"\n{len(rows) - len(bad)} of {len(rows)} places found. Saved to {OUT}")
    for r in bad:
        print(f"  CHECK {r['name']} ({r['destination']}): {r['status']} {r.get('error', '')}")
    if bad:
        print("Fix these by editing the 'query' in starter_places.json (or lat/lng in places_geocoded.json) and re-run.")
    return 0


def pick_image(summary: dict) -> str | None:
    """A sharp but not huge picture: the original if it is at most 1600 px wide, else a 960 px thumbnail."""
    original, thumb = summary.get("originalimage") or {}, (summary.get("thumbnail") or {}).get("source")
    if original.get("source") and original.get("width", 99999) <= 1600:
        return original["source"]
    if thumb and "/thumb/" in thumb:
        return re.sub(r"/\d+px-", "/960px-", thumb, count=1)
    return thumb


WIKI_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
GENERIC = {
    "fort", "lake", "mosque", "valley", "park", "national", "museum", "beach", "view", "point", "viewpoint",
    "bazaar", "street", "food", "old", "city", "shrine", "tomb", "garden", "gardens", "the", "and", "pass",
}


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in GENERIC}


def same_subject(found: str, name: str) -> bool:
    """A search hit is only accepted when it shares a distinctive word with the place name."""
    want = tokens(name) or {w for w in re.findall(r"[a-z]{3,}", name.lower())}
    return bool(want & tokens(found)) or bool(want & {w for w in re.findall(r"[a-z]{3,}", found.lower())})


def _wiki_summary(http: httpx.Client, title: str) -> dict | None:
    r = http.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}")
    if r.status_code != 200:
        return None
    data = r.json()
    return data if data.get("type") == "standard" else None


def _wiki_search(http: httpx.Client, query: str) -> str | None:
    r = http.get(WIKI_API, params={"action": "opensearch", "search": query, "limit": 1, "namespace": 0, "format": "json"})
    if r.status_code != 200:
        return None
    data = r.json()
    return data[1][0] if len(data) > 1 and data[1] else None


def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


def _commons_photo(http: httpx.Client, row: dict) -> tuple[str, str, str] | None:
    """(image url, credit, file page) for a freely licensed photo on Wikimedia Commons, or None."""
    for query in (f"{row['name']} {row['destination']}", row["name"]):
        r = http.get(COMMONS_API, params={
            "action": "query", "generator": "search", "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6,
            "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 960, "format": "json",
        })
        if r.status_code != 200:
            continue
        pages = sorted(((r.json().get("query") or {}).get("pages") or {}).values(), key=lambda p: p.get("index", 0))
        for page in pages:
            info = (page.get("imageinfo") or [{}])[0]
            title = page.get("title", "")
            meta = info.get("extmetadata") or {}
            licence = _strip_html((meta.get("LicenseShortName") or {}).get("value", ""))
            if not title.lower().endswith((".jpg", ".jpeg")) or info.get("width", 0) < 800:
                continue
            if not (licence.startswith("CC") or licence.lower().startswith("public domain")):
                continue
            if not same_subject(title, row["name"]):
                continue
            url = info.get("thumburl") or info.get("url")
            if not url:
                continue
            artist = _strip_html((meta.get("Artist") or {}).get("value", ""))[:60] or "Unknown author"
            return url, f"{artist}, {licence}, Wikimedia Commons", info.get("descriptionurl") or ""
        time.sleep(0.3)
    return None


def add_wikipedia(http: httpx.Client, row: dict) -> None:
    """Finds a photo: the Wikipedia article first (by title, then by search), then Wikimedia Commons."""
    try:
        summary = _wiki_summary(http, row.get("wiki") or row["name"])
        if not (summary and pick_image(summary)):
            for query in (f"{row['name']} {row['destination']}", f"{row['name']} Pakistan"):
                title = _wiki_search(http, query)
                time.sleep(0.3)
                if title and same_subject(title, row["name"]):
                    summary = _wiki_summary(http, title)
                    if summary and pick_image(summary):
                        break
                summary = None
        if summary and pick_image(summary):
            row["image_url"] = pick_image(summary)
            row["image_credit"] = "Wikipedia"
            page = ((summary.get("content_urls") or {}).get("desktop") or {}).get("page")
            if page:
                row["source_url"] = page
        else:
            found = _commons_photo(http, row)
            if found:
                row["image_url"], row["image_credit"] = found[0], found[1]
                if found[2]:
                    row["source_url"] = found[2]
        row["wiki_done"] = True
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    time.sleep(0.3)


def add_photos(settings: Settings) -> int:
    """Looks up photos for places that already have coordinates and no photo. Safe to re-run."""
    rows = load(OUT)
    if not rows:
        print("No data/places_geocoded.json yet. Run with --geocode first.")
        return 1
    todo = [r for r in rows if r.get("status") in ("ok", "review") and not r.get("image_url")]
    print(f"{len(todo)} places need a photo.")
    with httpx.Client(headers={"User-Agent": settings.user_agent}, timeout=20, follow_redirects=True) as http:
        for i, row in enumerate(todo, 1):
            add_wikipedia(http, row)
            print(f"[{i:>3}/{len(todo)}] {'photo' if row.get('image_url') else 'none ':<5} {row['name']}")
            save(rows)
    have = sum(1 for r in rows if r.get("image_url"))
    print(f"\n{have} of {len(rows)} places now have a photo. Restart the server to see them.")
    print("Places without one show a soft map pattern. You can paste a photo link in Admin.")
    return 0


def build_items(rows: list[dict]) -> tuple[list[tuple[str, dict]], list[str]]:
    """Validates geocoded rows. Returns (id, data) pairs ready to store, plus a list of skipped places."""
    items, skipped = [], []
    for row in rows:
        if row.get("status") not in ("ok", "review") or "lat" not in row:
            skipped.append(f"{row['name']} (no coordinates)")
            continue
        if row["status"] == "review" and not in_pakistan(row["lat"], row["lng"]):
            skipped.append(f"{row['name']} (outside Pakistan, fix the query)")
            continue
        payload = {k: row.get(k) for k in PlaceCreate.model_fields if k != "id" and row.get(k) is not None}
        try:
            place = PlaceCreate(**payload)
        except ValueError as exc:
            skipped.append(f"{row['name']} (invalid: {str(exc).splitlines()[0]})")
            continue
        items.append((places_svc.slugify(f"{place.name}-{place.destination}"), place.model_dump()))
    return items, skipped


async def import_places(settings: Settings, overwrite: bool, dry_run: bool) -> int:
    from pymongo import AsyncMongoClient

    from app.db import ensure_indexes

    rows = load(OUT)
    if not rows:
        print("No data/places_geocoded.json yet. Run with --geocode first.")
        return 1
    items, skipped = build_items(rows)

    if dry_run:
        print(f"Dry run: {len(items)} valid places, {len(skipped)} skipped.")
    else:
        client = AsyncMongoClient(settings.mongodb_uri, tz_aware=True)
        try:
            db = client[settings.mongodb_db]
            await ensure_indexes(db)
            if not overwrite:
                existing = {d["_id"] async for d in db.places.find({}, {"_id": 1})}
                kept = [i for i in items if i[0] in existing]
                items = [i for i in items if i[0] not in existing]
                if kept:
                    print(f"Leaving {len(kept)} existing places untouched (use --overwrite to replace them).")
            await places_svc.upsert_many(db, items)
            print(f"Imported {len(items)} places into '{settings.mongodb_db}'.")
        finally:
            await client.close()
    for s in skipped:
        print("  skipped:", s)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--geocode", action="store_true", help="look up coordinates on OpenStreetMap")
    ap.add_argument("--wiki", action="store_true", help="with --geocode: add Wikipedia image and link")
    ap.add_argument("--photos", action="store_true", help="find photos for places that already have coordinates")
    ap.add_argument("--email", help="contact email for OpenStreetMap (or set NOMINATIM_CONTACT_EMAIL)")
    ap.add_argument("--import", dest="do_import", action="store_true", help="write places to MongoDB")
    ap.add_argument("--overwrite", action="store_true", help="with --import: replace existing places")
    ap.add_argument("--dry-run", action="store_true", help="with --import: validate only")
    args = ap.parse_args()
    os.environ.setdefault("JWT_SECRET", "not-used-by-this-script-" + "x" * 24)  # Settings needs one; seeding does not
    settings = Settings(nominatim_contact_email=args.email) if args.email else Settings()
    if args.geocode:
        return geocode(settings, args.wiki)
    if args.photos:
        return add_photos(settings)
    if args.do_import:
        return asyncio.run(import_places(settings, args.overwrite, args.dry_run))
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
