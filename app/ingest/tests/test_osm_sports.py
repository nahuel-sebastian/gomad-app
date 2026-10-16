import os
import pathlib

import pytest
import yaml

from build_db import apply_activities
from common import CONFIG_DIR, RAW, assign_municipality
from normalize.sports import COLUMNS, osm_default_name, osm_sport_tags, osm_sports

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
    assert set(g.index) == {"osm:way/1", "osm:way/4", "osm:node/8", "osm:relation/9", "osm:way/11"}
    assert (g["source"] == "osm_sport").all() and g.crs.to_epsg() == 4326
    assert (g.geometry.geom_type == "Point").all() and (g["type"] == "facility").all()
    assert g.loc["osm:way/1", "sports"] == ["swimming", "tennis"] and g.loc["osm:way/1", "name"] == "Forus Getafe"
    assert g.loc["osm:way/4", "name"] == "Pista de baloncesto (OpenStreetMap)"
    assert g.loc["osm:way/4", "covered"] == False                       # pista: al aire libre
    assert g.loc["osm:relation/9", "facility_type"] == "stadium"
    assert g.loc["osm:node/8", "source_id"] == "node/8"
    assert g.loc["osm:way/1", "geometry"].x == pytest.approx(-3.74 + 0.00025, abs=1e-4)


def test_named_centre_inherits_sports_of_its_pitches():
    # criterio propio (16/10): polideportivos con nombre sin sport=* (los de Getafe) toman los deportes de sus pistas
    g = osm_sports(SAMPLE).set_index("id")
    assert g.loc["osm:way/11", "sports"] == ["padel", "tennis"]           # la pista privada no cuenta
    assert g.loc["osm:way/11", "name"] == "Polideportivo Juan de la Cierva"
    assert not {"osm:way/12", "osm:way/13", "osm:way/15", "osm:way/16"} & set(g.index)


def as_destination_raw(g):
    # mismas columnas que clean/destination_raw.parquet (run() reindexa a COLUMNS)
    return g.reindex(columns=[*COLUMNS, "access"])


def load_activities():
    """Solo las reglas source: osm_sport (apply_activities falla con fuentes sin filas, y aqui solo hay OSM)."""
    cfg = yaml.safe_load((CONFIG_DIR / "activities.yaml").read_text(encoding="utf-8"))
    return {"activities": [{**a, "rules": [r for r in a["rules"] if r["source"] == "osm_sport"]}
                           for a in cfg["activities"]]}


def test_activity_rules_for_osm():
    acts = apply_activities(as_destination_raw(osm_sports(SAMPLE).assign(ine_code="28065")), load_activities())
    got = set(zip(acts["destination_id"], acts["activity"]))
    assert {("osm:way/1", "swim"), ("osm:way/1", "tennis"), ("osm:way/4", "basketball"),
            ("osm:node/8", "swim"), ("osm:relation/9", "run")} <= got
    assert set(acts["suitability"]) == {0.8}


@pytest.mark.slow
def test_getafe_has_swim_tennis_basketball():
    pbf = RAW / "osm" / "madrid-latest.osm.pbf"
    if not pbf.exists():
        pytest.skip("falta el extracto OSM (download_sources.py --only osm)")
    g = assign_municipality(osm_sports(pbf))
    getafe = g[g["ine_code"] == "28065"]
    acts = apply_activities(as_destination_raw(getafe), load_activities())
    assert {"swim", "tennis", "basketball"} <= set(acts["activity"])
    pools = getafe[getafe["facility_type"] == "swimming_pool"]
    assert (pools["access"] != "private").all()
    assert ((pools["name"] != "Piscina (OpenStreetMap)") | (pools["access"] == "public")).all()


def test_osm_sport_municipalities_in_config():
    cfg = yaml.safe_load((CONFIG_DIR / "activities.yaml").read_text(encoding="utf-8"))
    assert cfg["osm_sport_municipalities"] == ["28065", "28079", "28148", "28040"]


def test_osm_reader_uses_one_thread():
    # con el pool de hilos por defecto, libosmium se bloquea a menudo en Windows
    osm_sports(SAMPLE)
    assert os.environ["OSMIUM_POOL_THREADS"] == "1"


@pytest.mark.slow
def test_osm_sports_keeps_only_listed_municipalities():
    assert set(osm_sports(SAMPLE, ine_codes=["28065"])["ine_code"]) == {"28065"}
    assert osm_sports(SAMPLE, ine_codes=["28079"]).empty
