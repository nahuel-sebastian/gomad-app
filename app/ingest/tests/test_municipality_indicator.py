import duckdb
import pandas as pd
import pytest
import yaml

import build_db
from common import CLEAN, CONFIG_DIR

MINI = {"population_year": 2025, "indicators": [
    {"key": "a_per_1000", "category": "health", "label": "A", "source": ["farmacias", "padron"], "unit": "u",
     "no_rows": "zero", "year": None},
    {"key": "b", "category": "sport", "label": "B", "source": ["nmc_deporte"], "unit": "u", "no_rows": "null",
     "year": 2023}]}


def test_zero_rule_versus_null_rule():
    values = {"a_per_1000": pd.Series({"28065": 3.0, "28999": 1.0}), "b": pd.Series({"28065": 0.0})}
    t = build_db.indicator_table(MINI, ["28065", "28107"], values)
    assert list(t.columns) == ["ine_code", "category", "key", "value", "unit", "year", "source"]
    got = {(r.ine_code, r.key): r.value for r in t.itertuples()}
    assert len(t) == 4 and ("28999", "a_per_1000") not in got     # solo los municipios pedidos
    assert got[("28065", "a_per_1000")] == 3.0 and got[("28107", "a_per_1000")] == 0.0   # zero: sin filas = 0
    assert got[("28065", "b")] == 0.0 and pd.isna(got[("28107", "b")])   # null: sin filas = NULL; 0 real se queda
    assert set(t.loc[t.key == "a_per_1000", "source"]) == {"farmacias"}   # primera fuente de la lista
    con = duckdb.connect()
    build_db.store_indicators(con, t)
    assert con.execute("SELECT count(*) FROM municipality_indicator WHERE value IS NULL").fetchone()[0] == 1
    assert con.execute("SELECT year FROM municipality_indicator WHERE key='b' AND ine_code='28065'").fetchone() == (2023,)
    assert con.execute("SELECT year FROM municipality_indicator WHERE key='a_per_1000' LIMIT 1").fetchone() == (None,)


def test_frame_values_carry_row_source_and_year():
    # Task 170: un DataFrame da fuente (ids separados por comas) y año por municipio; los ausentes, regla no_rows
    frame = pd.DataFrame({"value": [7.0], "source": ["nmc_deporte,osm"], "year": [None]}, index=["28065"])
    t = build_db.indicator_table(MINI, ["28065", "28107"], {"a_per_1000": pd.Series(dtype=float), "b": frame})
    rows = {r.ine_code: r for r in t[t.key == "b"].itertuples()}
    assert rows["28065"].value == 7.0 and rows["28065"].source == "nmc_deporte,osm" and pd.isna(rows["28065"].year)
    assert pd.isna(rows["28107"].value) and rows["28107"].source == "nmc_deporte" and rows["28107"].year == 2023


def test_indicator_without_calculation_fails_readably():
    with pytest.raises(ValueError, match=r"«b».*no se sabe calcular"):
        build_db.indicator_table(MINI, ["28065"], {"a_per_1000": pd.Series(dtype=float)})


def test_rate_divides_by_population():
    rate = build_db.per_1000(pd.Series({"28065": 2}), pd.Series({"28065": 1000, "28107": 500}))
    assert rate.to_dict() == {"28065": 2.0}


def test_rate_without_population_fails_readably():
    # sin poblacion la tasa seria NaN y la regla zero la convertiria en 0 sin avisar
    with pytest.raises(ValueError, match="28107"):
        build_db.per_1000(pd.Series({"28065": 2, "28107": 1}), pd.Series({"28065": 1000}))


def test_missing_shapefile_fails_readably(tmp_path, monkeypatch):
    (tmp_path / "nmc_deporte").mkdir()
    monkeypatch.setattr(build_db, "RAW", tmp_path)
    with pytest.raises(FileNotFoundError, match="nmc_deporte"):
        build_db._shp("nmc_deporte")


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    path = build_db.build_main(tmp_path_factory.mktemp("db") / "gomad.duckdb")   # activities.yaml real (8)
    return duckdb.connect(str(path), read_only=True)


def value(db, ine, key):
    return db.execute("SELECT value FROM municipality_indicator WHERE ine_code=? AND key=?", [ine, key]).fetchone()[0]


@pytest.mark.slow
def test_179_by_14_in_yaml_order(db):
    cfg = yaml.safe_load((CONFIG_DIR / "indicators.yaml").read_text(encoding="utf-8"))
    assert db.execute("SELECT count(*), count(DISTINCT ine_code) FROM municipality_indicator").fetchone() == (179 * 14, 179)
    keys = [k for (k,) in db.execute("SELECT key FROM municipality_indicator WHERE ine_code='28065' ORDER BY rowid").fetchall()]
    assert keys == [i["key"] for i in cfg["indicators"]]
    for ind in cfg["indicators"]:
        rows = db.execute("SELECT DISTINCT category, unit, year, source FROM municipality_indicator WHERE key=?",
                          [ind["key"]]).fetchall()
        assert rows == [(ind["category"], ind["unit"], ind["year"], ind["source"][0])]
    zero_keys = [i["key"] for i in cfg["indicators"] if i["no_rows"] == "zero"]
    nulls = db.execute(f"SELECT count(*) FROM municipality_indicator WHERE value IS NULL AND key IN "
                       f"({', '.join('?' * len(zero_keys))})", zero_keys).fetchone()[0]
    assert nulls == 0                                              # regla zero: nunca NULL


@pytest.mark.slow
def test_patones_without_nomecalles_is_null(db):
    assert value(db, "28107", "sport_facilities") is None          # Patones: NULL, no 0
    assert value(db, "28107", "sport_facilities_per_1000") is None
    assert value(db, "28065", "sport_facilities") > 0


@pytest.mark.slow
def test_green_null_outside_vpla(db):
    assert value(db, "28079", "green_m2_per_inhabitant") is None   # Madrid, sin VPLA
    assert value(db, "28065", "green_m2_per_inhabitant") > 0       # Getafe
    assert value(db, "28016", "green_m2_per_inhabitant") == 0      # en VPLA sin zonas verdes: 0, no «sin datos»
    leaked = db.execute("SELECT count(*) FROM municipality_indicator i JOIN municipality m USING (ine_code) "
                        "WHERE i.key='green_m2_per_inhabitant' AND NOT m.in_vpla AND i.value IS NOT NULL").fetchone()[0]
    assert leaked == 0


@pytest.mark.slow
def test_health_centres_total(db):
    # division: 429; la descarga del 16/10 trae 430 (Ruling de la Task 33)
    assert db.execute("SELECT sum(value) FROM municipality_indicator WHERE key='health_centres'").fetchone()[0] == 430


@pytest.mark.slow
@pytest.mark.parametrize("key, covered", [
    ("sport_facilities", 178), ("sport_facilities_per_1000", 178), ("catalog_activities", 179),
    ("green_m2_per_inhabitant", 167),   # ficha: 162; hoy in_vpla = 167 (Ruling)
    ("drove_roads_km", 171),            # ficha: 169 (Ruling: 28077 y 289xx por cruce espacial)
    ("recreation_areas", 55), ("bus_stops_per_1000", 179),
    ("rail_stations", 39),              # ficha: metro 15, cercanias 33 (hoy 34); union 39
    ("health_centres", 179), ("pharmacies_per_1000", 160), ("aed_per_1000", 172), ("schools", 156),
    ("good_3g_pct", 155), ("social_centres", 138)])
def test_coverage(db, key, covered):
    # cobertura = municipios con dato > 0, salvo good_3g_pct y green (con dato, aunque sea 0)
    cond = "value IS NOT NULL" if key in ("good_3g_pct", "green_m2_per_inhabitant") else "value > 0"
    assert db.execute(f"SELECT count(*) FROM municipality_indicator WHERE key=? AND {cond}", [key]).fetchone()[0] == covered


@pytest.mark.slow
def test_rates_and_units_are_plausible(db):
    pop = pd.read_parquet(CLEAN / "population.parquet").query("year == 2025").set_index("ine_code")["population"]
    schools_getafe = value(db, "28065", "schools")
    assert value(db, "28065", "aed_per_1000") > 0 and value(db, "28065", "bus_stops_per_1000") > 0
    assert 0 <= db.execute("SELECT min(value) FROM municipality_indicator WHERE key='good_3g_pct'").fetchone()[0]
    assert db.execute("SELECT max(value) FROM municipality_indicator WHERE key='good_3g_pct'").fetchone()[0] <= 100
    assert db.execute("SELECT max(value) FROM municipality_indicator WHERE key='catalog_activities'").fetchone()[0] <= 8
    assert schools_getafe == int(schools_getafe) and pop["28065"] > 100_000
    assert 250 < value(db, "28079", "drove_roads_km") < 300       # Madrid: tramos 28906–28912 (272 km)


@pytest.mark.slow
def test_lozoyuela_gets_its_old_code_drove_roads(db):
    # 28077 es el codigo antiguo de Lozoyuela-Navas-Sieteiglesias (28901): 11 tramos, ~62 km
    assert 55 < value(db, "28901", "drove_roads_km") < 70
