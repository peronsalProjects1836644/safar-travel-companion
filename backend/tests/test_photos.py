import httpx
import pytest
import respx

from scripts import seed_places as sp

SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"


def summary(title, thumb=True):
    body = {"type": "standard", "title": title, "content_urls": {"desktop": {"page": f"https://en.wikipedia.org/wiki/{title}"}}}
    if thumb:
        body["thumbnail"] = {"source": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/X.jpg/320px-X.jpg", "width": 320}
    return httpx.Response(200, json=body)


def commons(title, licence="CC BY-SA 4.0", width=2000):
    return httpx.Response(200, json={"query": {"pages": {"1": {
        "title": title, "index": 1,
        "imageinfo": [{"thumburl": "https://upload.wikimedia.org/thumb/960px-C.jpg", "url": "https://upload.wikimedia.org/C.jpg",
                       "width": width, "descriptionurl": "https://commons.wikimedia.org/wiki/File:C.jpg",
                       "extmetadata": {"LicenseShortName": {"value": licence}, "Artist": {"value": '<a href="x">Sara Khan</a>'}}}],
    }}}})


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(sp.time, "sleep", lambda *_: None)


def run(row):
    with httpx.Client() as http:
        sp.add_wikipedia(http, row)
    return row


def test_wikipedia_article_by_title_gives_a_960px_photo_and_credit():
    row = {"name": "Badshahi Mosque", "destination": "Lahore"}
    with respx.mock() as r:
        r.get(SUMMARY + "Badshahi_Mosque").mock(return_value=summary("Badshahi_Mosque"))
        run(row)
    assert row["image_url"].endswith("/960px-X.jpg") and row["image_credit"] == "Wikipedia"
    assert row["source_url"].endswith("/Badshahi_Mosque") and row["wiki_done"]


def test_wikipedia_search_finds_the_article_when_the_title_does_not_match():
    row = {"name": "Hussaini Suspension Bridge", "destination": "Hunza"}
    with respx.mock() as r:
        r.get(SUMMARY + "Hussaini_Suspension_Bridge").mock(return_value=httpx.Response(404))
        r.get(sp.WIKI_API).mock(return_value=httpx.Response(200, json=["q", ["Hussaini Bridge"], [], []]))
        r.get(SUMMARY + "Hussaini_Bridge").mock(return_value=summary("Hussaini_Bridge"))
        run(row)
    assert row["image_credit"] == "Wikipedia" and "Hussaini_Bridge" in row["source_url"]


def test_an_unrelated_search_result_is_rejected_then_commons_is_used():
    row = {"name": "Passu Cones", "destination": "Hunza"}
    with respx.mock() as r:
        r.get(SUMMARY + "Passu_Cones").mock(return_value=httpx.Response(404))
        r.get(sp.WIKI_API).mock(return_value=httpx.Response(200, json=["q", ["Cricket"], [], []]))
        r.get(sp.COMMONS_API).mock(return_value=commons("File:Passu Cones from Karakoram Highway.jpg"))
        run(row)
    assert row["image_credit"] == "Sara Khan, CC BY-SA 4.0, Wikimedia Commons"
    assert row["image_url"].endswith("960px-C.jpg") and "commons.wikimedia.org" in row["source_url"]


def test_commons_files_with_other_licences_small_size_or_wrong_subject_are_skipped():
    for resp in (
        commons("File:Passu Cones.jpg", licence="All rights reserved"),
        commons("File:Passu Cones.jpg", width=400),
        commons("File:Random cat.jpg"),
        commons("File:Passu Cones.png"),
    ):
        row = {"name": "Passu Cones", "destination": "Hunza"}
        with respx.mock() as r:
            r.get(SUMMARY + "Passu_Cones").mock(return_value=httpx.Response(404))
            r.get(sp.WIKI_API).mock(return_value=httpx.Response(200, json=["q", [], [], []]))
            r.get(sp.COMMONS_API).mock(return_value=resp)
            run(row)
        assert "image_url" not in row and row["wiki_done"]


def test_a_network_error_leaves_the_row_untouched():
    row = {"name": "Passu Cones", "destination": "Hunza"}
    with respx.mock() as r:
        r.get(url__regex=r".*").mock(side_effect=httpx.ConnectError("down"))
        run(row)
    assert "image_url" not in row and "wiki_done" not in row


# ---- coordinates for places OpenStreetMap search does not find

def locate(place, **settings_kw):
    from app.core.config import Settings
    settings = Settings(jwt_secret="x" * 40, nominatim_contact_email="a@b.com", **settings_kw)
    row = {**place, "status": "missing"}
    with httpx.Client() as http:
        sp.find_coordinates(http, settings, place, row)
    return row


PLACE = {"name": "Fairy Meadows", "destination": "Gilgit", "query": "Fairy Meadows, Gilgit-Baltistan"}


def test_an_alternative_openstreetmap_query_can_find_the_place():
    answers = iter([httpx.Response(200, json=[]), httpx.Response(200, json=[{"lat": "35.42", "lon": "74.58", "display_name": "Fairy Meadows"}])])
    with respx.mock() as r:
        r.get(sp.NOMINATIM_URL).mock(side_effect=lambda request: next(answers))
        row = locate(PLACE)
    assert row["status"] == "ok" and row["lat"] == 35.42 and row["matched"] == "Fairy Meadows"


def test_wikipedia_coordinates_are_used_when_openstreetmap_has_nothing():
    with respx.mock() as r:
        r.get(sp.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=[]))
        r.get(sp.WIKI_API, params={"action": "opensearch"}).mock(return_value=httpx.Response(200, json=["q", ["Fairy Meadows"], [], []]))
        r.get(sp.WIKI_API, params={"action": "query"}).mock(return_value=httpx.Response(200, json={"query": {"pages": {"9": {"coordinates": [{"lat": 35.4, "lon": 74.59}]}}}}))
        row = locate(PLACE)
    assert row["status"] == "ok" and (row["lat"], row["lng"]) == (35.4, 74.59) and row["matched"] == "Wikipedia: Fairy Meadows"


def test_a_result_outside_pakistan_is_flagged_for_review_and_nothing_found_stays_missing():
    with respx.mock() as r:
        r.get(sp.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=[{"lat": "48.8", "lon": "2.3", "display_name": "Paris"}]))
        assert locate(PLACE)["status"] == "review"
    with respx.mock() as r:
        r.get(sp.NOMINATIM_URL).mock(return_value=httpx.Response(200, json=[]))
        r.get(sp.WIKI_API).mock(return_value=httpx.Response(200, json=["q", [], [], []]))
        assert locate(PLACE)["status"] == "missing"
