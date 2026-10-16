import pathlib

import pytest

from normalize.sports import osm_default_name, osm_sport_tags, osm_sports

SAMPLE = pathlib.Path(__file__).parent / "data" / "osm_sports_sample.osm"


@pytest.mark.parametrize("tags,expected", [
    ({"leisure": "sports_centre", "sport": "swimming;tennis", "name": "Forus"}, ["swimming", "tennis"]),
    ({"leisure": "stadium", "sport": " Athletics ", "name": "Estadio"}, ["athletics"]),
    ({"leisure": "sports_centre", "sport": "tennis"}, None),
    ({"leisure": "sports_centre", "name": "Centro"}, None),
    ({"leisure": "pitch", "sport": "tennis"}, None),
    ({"leisure": "pitch", "sport": "basketball", "access": "public"}, ["basketball"]),
    ({"leisure": "pitch", "sport": "padel", "access": "yes"}, ["padel"]),
    ({"leisure": "pitch", "sport": "soccer;basketball", "name": "Pistas"}, ["basketball"]),
    ({"leisure": "pitch", "sport": "soccer", "name": "Campo"}, None),
    ({"leisure": "pitch", "sport": "tennis", "access": "private", "name": "Club"}, ["tennis"]),
    ({"leisure": "swimming_pool"}, None),
    ({"leisure": "swimming_pool", "name": "Piscina comunitaria", "access": "private"}, None),
    ({"leisure": "swimming_pool", "access": "yes"}, None),
    ({"leisure": "swimming_pool", "access": "public"}, ["swimming"]),
    ({"leisure": "swimming_pool", "name": "Piscina Municipal"}, ["swimming"]),
    ({"amenity": "school", "sport": "tennis", "name": "Colegio"}, None),
])
def test_osm_filter_rules(tags, expected):
    assert osm_sport_tags(tags) == expected


def test_default_names():
    assert osm_default_name({"leisure": "pitch", "sport": "tennis"}, ["tennis"]) == "Pista de tenis (OpenStreetMap)"
    assert osm_default_name({"leisure": "pitch"}, ["basketball"]) == "Pista de baloncesto (OpenStreetMap)"
    assert osm_default_name({"leisure": "pitch"}, ["padel"]) == "Pista de pádel (OpenStreetMap)"
    assert osm_default_name({"leisure": "swimming_pool"}, ["swimming"]) == "Piscina (OpenStreetMap)"
    assert osm_default_name({"leisure": "pitch", "name": " Pistas Buenavista "}, ["tennis"]) == "Pistas Buenavista"


def test_osm_sports_reads_sample():
    g = osm_sports(SAMPLE).set_index("id")
    assert set(g.index) == {"osm:way/1", "osm:way/4", "osm:node/8", "osm:relation/9"}
    assert (g["source"] == "osm_sport").all() and g.crs.to_epsg() == 4326
    assert (g.geometry.geom_type == "Point").all() and (g["type"] == "facility").all()
    assert g.loc["osm:way/1", "sports"] == ["swimming", "tennis"] and g.loc["osm:way/1", "name"] == "Forus Getafe"
    assert g.loc["osm:way/4", "name"] == "Pista de baloncesto (OpenStreetMap)"
    assert g.loc["osm:way/4", "covered"] == False                       # pista: al aire libre
    assert g.loc["osm:relation/9", "facility_type"] == "stadium"
    assert g.loc["osm:node/8", "source_id"] == "node/8"
    assert g.loc["osm:way/1", "geometry"].x == pytest.approx(-3.74 + 0.00025, abs=1e-4)
