import pandas as pd

import normalize.air as air


def test_readings_skip_a_source_without_valid_csv(tmp_path, monkeypatch):
    # equipo nuevo con el CSV del Ayuntamiento vacio y sin uno anterior: el resto se normaliza igual
    def latest(folder, columns):
        if folder.name == "ay_aire":
            raise FileNotFoundError("Ningún CSV de ay_aire tiene las columnas")
        return folder / "dia.csv"

    seen = []
    monkeypatch.setattr(air, "RAW", tmp_path / "raw")
    monkeypatch.setattr(air, "CLEAN", tmp_path / "clean")
    monkeypatch.setattr(air, "latest_csv", latest)
    monkeypatch.setattr(air, "read_csv", lambda path, **kw: seen.append(path.parent.name) or pd.DataFrame())
    monkeypatch.setattr(air, "long_readings", lambda df: pd.DataFrame())
    air.run_readings()   # no lanza
    assert seen == ["aire_dia"]
