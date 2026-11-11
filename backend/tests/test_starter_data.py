import json
from pathlib import Path

from app.models.place import PlaceCreate
from app.services.places import slugify

ROWS = json.loads((Path(__file__).resolve().parent.parent / "data" / "starter_places.json").read_text(encoding="utf-8"))


def test_every_starter_place_is_valid_and_unique():
    ids = set()
    for row in ROWS:
        payload = {k: v for k, v in row.items() if k in PlaceCreate.model_fields and v is not None}
        PlaceCreate(**payload, lat=30.0, lng=70.0)  # coordinates are added later by the geocoding step
        assert row["query"] and "Pakistan" in row["query"] or row["query"].endswith("Pakistan"), row["name"]
        ids.add(slugify(f"{row['name']}-{row['destination']}"))
    assert len(ids) == len(ROWS)


def test_every_destination_has_enough_places_to_plan_a_day():
    counts = {}
    for row in ROWS:
        counts[row["destination"]] = counts.get(row["destination"], 0) + 1
    thin = {d: n for d, n in counts.items() if n < 3}
    assert thin == {"Larkana": 1}  # Mohenjo-daro is a single-site day trip


def test_risky_areas_carry_an_advisory():
    risky = {"Khyber Pass Viewpoint", "Fairy Meadows", "Derawar Fort", "Kund Malir Beach"}
    got = {r["name"] for r in ROWS if r.get("advisory")}
    assert risky <= got
