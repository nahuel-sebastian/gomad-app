import copy
import json

import pytest
import yaml

from common import CONFIG_DIR
from indicators import CATEGORIES, COMPANIONS, PROFILES, IndicatorConfigError, load, validate

DEC09_KEYS = ["sport_facilities", "sport_facilities_per_1000", "catalog_activities", "green_m2_per_inhabitant",
              "drove_roads_km", "recreation_areas", "bus_stops_per_1000", "rail_stations", "health_centres",
              "pharmacies_per_1000", "aed_per_1000", "schools", "good_3g_pct", "social_centres"]


@pytest.fixture
def real():
    return yaml.safe_load((CONFIG_DIR / "indicators.yaml").read_text(encoding="utf-8"))


def test_real_yaml_is_valid_with_dec09_indicators():
    cfg = load()
    assert [i["key"] for i in cfg["indicators"]] == DEC09_KEYS
    by_key = {i["key"]: i for i in cfg["indicators"]}
    assert by_key["sport_facilities"]["no_rows"] == "null" and by_key["health_centres"]["no_rows"] == "zero"
    assert by_key["green_m2_per_inhabitant"]["no_rows"] == "null" and by_key["good_3g_pct"]["no_rows"] == "null"
    assert sum(i["no_rows"] == "null" for i in cfg["indicators"]) == 4
    assert by_key["good_3g_pct"]["year"] == 2023 and cfg["population_year"] == 2025
    fit = cfg["fit"]
    assert fit["own_criterion"] is True
    assert fit["profiles"]["senior"] == ["health_centres", "aed_per_1000"]
    assert fit["profiles"]["stroller"] == ["green_m2_per_inhabitant"]
    assert fit["companions"]["kids"] == ["schools"]
    assert fit["companions"]["dog"] == {"route_poi": "dog_area", "when_absent": "no_data"}


def test_unknown_category_fails_readably(real):
    real["indicators"][3]["category"] = "green"
    with pytest.raises(IndicatorConfigError, match=r"green_m2_per_inhabitant.*categoría «green»"):
        validate(real)


def test_duplicate_key_fails_readably(real):
    real["indicators"].append(copy.deepcopy(real["indicators"][0]))
    with pytest.raises(IndicatorConfigError, match=r"clave repetida.*sport_facilities"):
        validate(real)


def test_missing_required_field_fails_readably(real):
    del real["indicators"][8]["unit"]
    with pytest.raises(IndicatorConfigError, match=r"health_centres.*falta «unit»"):
        validate(real)


@pytest.mark.parametrize("change, message", [
    (lambda c: c["indicators"][0].update(no_rows="cero"), r"sport_facilities.*no_rows"),
    (lambda c: c["fit"]["profiles"].update(elderly=["schools"]), r"perfil «elderly»"),
    (lambda c: c["fit"]["companions"].update(kids=["playgrounds"]), r"indicador «playgrounds»"),
])
def test_bad_values_fail_readably(real, change, message):
    change(real)
    with pytest.raises(IndicatorConfigError, match=message):
        validate(real)


def test_contract_enums_in_sync(root):
    schemas = json.loads((root.parent / "frontend" / "src" / "api" / "openapi.json")
                         .read_text(encoding="utf-8"))["components"]["schemas"]
    assert list(CATEGORIES) == schemas["Indicator"]["properties"]["category"]["enum"]
    assert list(PROFILES) == schemas["RecommendRequest"]["properties"]["profile"]["enum"]
    assert list(COMPANIONS) == schemas["RecommendRequest"]["properties"]["companions"]["items"]["enum"]


@pytest.mark.parametrize("change, message", [
    (lambda c: c["indicators"][0].update(year=True), r"sport_facilities.*«year» True"),
    (lambda c: c["indicators"].append("health_centres"), r"n\.º 15.*mapa"),
    (lambda c: c["fit"].update(met_if_above="0"), r"met_if_above"),
    (lambda c: c["fit"]["companions"]["dog"].update(route_poi="dog_park"), r"route_poi «dog_park»"),
])
def test_more_bad_values_fail_readably(real, change, message):
    change(real)
    with pytest.raises(IndicatorConfigError, match=message):
        validate(real)


def test_catalog_unit_follows_activities_yaml(real):
    n = len(yaml.safe_load((CONFIG_DIR / "activities.yaml").read_text(encoding="utf-8"))["activities"])
    assert validate(copy.deepcopy(real), activities_count=n)
    with pytest.raises(IndicatorConfigError, match=rf"catalog_activities.*«de {n}»"):
        validate(real, activities_count=n + 1)


def test_poi_types_in_sync_with_route_poi():
    from graph import OSM_POI
    from indicators import POI_TYPES
    from normalize.furniture import CITY_COUNCIL
    assert set(POI_TYPES) == set(OSM_POI.values()) | set(CITY_COUNCIL.values()) | {"aed"}
