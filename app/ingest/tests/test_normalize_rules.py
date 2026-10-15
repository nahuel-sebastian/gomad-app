import pandas as pd
import pytest

from normalize.furniture import working_from_status
from normalize.sports import eiel_covered


@pytest.mark.parametrize("facility_type,sup_cubi,expected", [
    ("PISCINAS AL AIRE LIBRE", "350", False),     # vestuario cubierto, piscina al aire libre
    ("TERRENOS DE JUEGO", "120", False),
    ("PISTAS POLIDEPORTIVAS", "80", False),
    ("FRONTONES (SIN CUBRIR)", "40", False),
    ("PISCINAS CUBIERTAS", "0", True),
    ("POLIDEPORTIVOS CUBIERTOS", "", True),
    ("GIMNASIO", "0", True),
    ("COMPLEJOS POLIDEPORTIVOS", "1500", True),   # mixto: decide la superficie cubierta
    ("COMPLEJOS POLIDEPORTIVOS", "0", False),
    ("OTROS", "", None),                          # sin datos: no se sabe
])
def test_eiel_covered(facility_type, sup_cubi, expected):
    assert eiel_covered(facility_type, sup_cubi) is expected


def test_working_from_status():
    # nulo = sin dato: un banco sin ESTADO no es un banco roto
    status = pd.Series(["OPERATIVO", "FUERA_DE_SERVICIO", "", "  "])
    working = working_from_status(status)
    assert str(working.dtype) == "boolean"
    assert working[:2].tolist() == [True, False]
    assert working[2:].isna().all()
