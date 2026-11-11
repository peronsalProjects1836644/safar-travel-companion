"""Check that this computer can reach the free services the app uses.

    python -m scripts.check_services

Prints one line per service, so you can see which one is blocked or down.
"""

import time

import httpx

from app.services.safety import OVERPASS_URLS

QUERY = '[out:json][timeout:15];nwr["amenity"="hospital"](around:3000,31.5700,74.3105);out center 3;'
HEADERS = {"User-Agent": "SmartTourCompanion/1.0 (service check)"}


def check(name: str, fn) -> None:
    start = time.time()
    try:
        detail = fn()
        print(f"  OK    {name} ({time.time() - start:.1f}s) {detail}")
    except Exception as exc:  # noqa: BLE001 - this script only reports
        print(f"  FAIL  {name}: {type(exc).__name__}: {exc}")


def main() -> None:
    with httpx.Client(headers=HEADERS, timeout=20) as http:
        for url in OVERPASS_URLS:
            def overpass(url=url):
                r = http.post(url, data={"data": QUERY})
                r.raise_for_status()
                return f"{len(r.json().get('elements', []))} hospitals found"
            check("Overpass " + url.split("/")[2], overpass)

        def weather():
            r = http.get("https://api.open-meteo.com/v1/forecast", params={"latitude": 31.55, "longitude": 74.34, "current": "temperature_2m"})
            r.raise_for_status()
            return f"{r.json()['current']['temperature_2m']} C in Lahore"
        check("Open-Meteo weather", weather)

        def wiki():
            r = http.get("https://en.wikipedia.org/api/rest_v1/page/summary/Badshahi_Mosque")
            r.raise_for_status()
            return "thumbnail " + ("found" if r.json().get("thumbnail") else "missing")
        check("Wikipedia", wiki)

        def tiles():
            r = http.get("https://tile.openstreetmap.org/5/22/13.png")
            r.raise_for_status()
            return f"{len(r.content)} bytes"
        check("OpenStreetMap map tiles", tiles)

        def nominatim():
            r = http.get("https://nominatim.openstreetmap.org/search", params={"q": "Badshahi Mosque Lahore", "format": "json", "limit": 1})
            r.raise_for_status()
            return f"{len(r.json())} result"
        check("Nominatim search", nominatim)


if __name__ == "__main__":
    main()
