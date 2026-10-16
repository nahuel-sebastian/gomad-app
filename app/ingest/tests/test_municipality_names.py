"""Nombre para mostrar de cada municipio: el del padron, con el articulo delante (no el de la capa, en MAYUSCULAS)."""
import pytest

from common import CLEAN, RAW


def test_display_name_moves_the_article():
    from normalize.municipalities import display_name
    assert display_name("Acebeda (La)") == "La Acebeda"
    assert display_name("Rozas de Madrid (Las)") == "Las Rozas de Madrid"
    assert display_name("Álamo (El)") == "El Álamo"
    assert display_name("Alcalá de Henares") == "Alcalá de Henares"
    assert display_name("  Getafe ") == "Getafe"


@pytest.mark.slow
def test_municipality_names_from_padron():
    if not (RAW / "padron").exists() or not (RAW / "municipios").exists():
        pytest.skip("sin app/data/raw/padron o municipios")
    import geopandas as gpd

    from normalize import load_all
    load_all()["municipality"]()
    m = gpd.read_parquet(CLEAN / "municipality.parquet").set_index("ine_code")["name"]
    assert len(m) == 179
    assert m["28065"] == "Getafe" and m["28005"] == "Alcalá de Henares"
    assert m["28127"] == "Las Rozas de Madrid" and m["28001"] == "La Acebeda"
    assert not any(n.isupper() for n in m)                       # ninguno en MAYUSCULAS
