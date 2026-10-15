import pathlib

import pandas as pd
import pytest

from common import CLEAN, to_wgs84
from normalize import load_all
from normalize.addresses import build, plain

SAMPLE = pathlib.Path(__file__).parent / "data" / "callejero_sample.csv"


def test_plain():
    assert plain("Cñada. de la Ñora-Vieja") == "cnada de la nora vieja"
    assert plain("  GRAN   Vía ") == "gran via"


def test_build_keeps_numbered_portals_and_streets():
    out = build(SAMPLE)
    assert len(out) == 3                                   # fuera: punto kilometrico (K) y portal sin numero (S)
    row = out[(out.ine_code == "28065") & (out.number == 10)].iloc[0]
    lon, lat = to_wgs84([437838.9803], [4461942.0104])
    assert row.lon == pytest.approx(lon[0]) and row.lat == pytest.approx(lat[0])
    assert (row.street, row.street_norm, row.street_type, row.municipality, row.street_code) == (
        "Madrid", "madrid", "Calle", "Getafe", "065A0460")
    assert out[out.number == 65].letter.item() == "B"
    street = out[out.ine_code == "28006"].iloc[0]
    assert pd.isna(street.number)
    assert street.street == "de la Constitución" and street.street_norm == "de la constitucion"
    assert not (out.municipality == "Galapagar").any()


@pytest.mark.slow
def test_addresses_real():
    load_all()["addresses"]()
    out = pd.read_parquet(CLEAN / "addresses.parquet")
    assert out.ine_code.nunique() == 179
    row = out[(out.ine_code == "28065") & (out.street_code == "065A0460") & (out.number == 10)].iloc[0]
    assert row.lon == pytest.approx(-3.7314934, abs=1e-6) and row.lat == pytest.approx(40.3056775, abs=1e-6)
    assert out.lon.between(-4.7, -3.0).all() and out.lat.between(39.8, 41.2).all()
