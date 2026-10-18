import copy

import pytest

import schemas as s
import settings
from ai.dictionary import Analysis, interpret_text, normalize, validate_assistant_config

EXAMPLE = "15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado"


@pytest.fixture(scope="module")
def cfg():
    return settings.load("assistant")


def params(text, cfg, analysis=None):
    res = interpret_text(text, analysis, cfg)
    assert res.clarification is None and res.rejection is None, res
    return res.params


def test_normalize():
    assert normalize("  Sin  CUESTAS, Kilómetros ") == "sin cuestas, kilometros"


def test_example_phrase(cfg):
    res = interpret_text(EXAMPLE, None, cfg)
    assert res.clarification is None and res.rejection is None
    assert res.params == s.AssistantParams(activity="walk", distance_km=15, loop=True,
                                           pass_by=["park", "fountain", "bench", "supermarket"], avoid=[])


def test_run_duration_and_one_way(cfg):
    p = params("quiero correr 45 minutos, solo ida, sin tráfico", cfg)
    assert (p.activity, p.duration_min, p.distance_km, p.loop, p.avoid) == ("run", 45, None, False, ["traffic"])
    assert params("media hora caminando", cfg).duration_min == 30
    assert params("pasear 2 horas", cfg).duration_min == 120
    assert params("800 m andando", cfg).distance_km == 0.8
    assert params("1,5 km", cfg).distance_km == 1.5


def test_multiword_and_negations(cfg):
    assert params("5 km por un parque infantil", cfg).pass_by == ["playground"]
    assert params("5 km sin cuestas", cfg).avoid == ["hills"]
    assert params("5 km con cuestas", cfg).avoid == []
    assert params("5 km sin pasar por supermercado", cfg).pass_by == []
    assert params("5 km por llano", cfg).avoid == ["hills"]
    assert params("5 km con mi perro", cfg).pass_by == ["dog_area"]
    p = params("5 km sin cuestas, con un parque", cfg)
    assert p.avoid == ["hills"] and p.pass_by == ["park"]


def test_medical_wins_over_route(cfg):
    for text in ("15 km con la rodilla operada", "¿Puedo correr con la tensión alta?"):
        res = interpret_text(text, None, cfg)
        assert res.params is None and "no da consejo médico" in res.rejection


def test_out_of_catalog(cfg):
    res = interpret_text("10 km en bici", None, cfg)
    assert res.params is None and "caminar o correr" in res.rejection


def test_ambiguous_asks(cfg):
    assert "¿Qué distancia o cuánto tiempo" in interpret_text("quiero dar un paseo", None, cfg).clarification
    assert "¿Quieres caminar o correr?" in interpret_text("correr o caminar 5 km", None, cfg).clarification
    res = interpret_text("60 km andando", None, cfg)
    assert res.params is None and "42 km" in res.clarification


def test_analysis_adds_phrases_and_quantities(cfg):
    p = params("ruta tranquila", cfg, Analysis(entities=[("10 km", "QUANTITY")], phrases=["parque"]))
    assert p.distance_km == 10 and p.pass_by == ["park"]


def test_config_is_valid(cfg):
    validate_assistant_config(cfg)
    bad = copy.deepcopy(cfg)
    bad["interpret"]["pass_by"]["castle"] = ["castillo"]
    with pytest.raises(ValueError):
        validate_assistant_config(bad)


def test_config_covers_every_pass_by(cfg):
    bad = copy.deepcopy(cfg)
    bad["route"]["poi_kinds"].remove("bench")
    with pytest.raises(ValueError):
        validate_assistant_config(bad)
    bad = copy.deepcopy(cfg)
    del bad["route"]["labels"]["hills"]
    with pytest.raises(ValueError):
        validate_assistant_config(bad)


def test_oci_phrases_do_not_undo_negations(cfg):
    # OCI devuelve «supermercado» suelto aunque el texto diga «sin pasar por supermercado» (comprobado el 18/10)
    p = params("5 km sin pasar por supermercado", cfg, Analysis(phrases=["supermercado"]))
    assert p.pass_by == []
    p = params("Quiero correr 10 km sin tráfico", cfg, Analysis(entities=[("10 km", "QUANTITY")],
                                                                  phrases=["10 km sin", "tráfico"]))
    assert p.avoid == ["traffic"] and p.distance_km == 10


def test_super_is_a_whole_word(cfg):
    assert params("5 km por la sierra superior", cfg).pass_by == []
    assert params("5 km y que pase por el súper", cfg).pass_by == ["supermarket"]


def test_clock_time_is_not_a_duration(cfg):
    p = params("a las 20 h 5 km", cfg)
    assert p.distance_km == 5 and p.duration_min is None
    assert interpret_text("a las 20 h", None, cfg).clarification is not None


@pytest.mark.parametrize("text,loop", [
    ("5 km ida y vuelta", True), ("5 km y volver a casa", True), ("5 km circular", True), ("5 km de vuelta", True),
    ("5 km solo ida", False), ("5 km sin volver", False), ("5 km hasta el parque", False),
    ("5 km hasta el parque y volver", True),
])
def test_round_trip_words(cfg, text, loop):
    assert params(text, cfg).loop is loop


@pytest.mark.parametrize("text", ["5 km hasta la fuente", "5 km hasta la plaza mayor"])
def test_hasta_place_is_one_way(cfg, text):
    assert params(text, cfg).loop is False


def test_hasta_clock_time_is_not_one_way(cfg):
    p = params("salir hasta las 9, 5 km", cfg)
    assert p.loop is True and p.distance_km == 5 and p.duration_min is None


@pytest.mark.parametrize("text", ["5 km hasta las nueve", "5 km hasta la una", "5 km hasta las Doce",
                                  "salir a las ocho, 5 km hasta las diez"])
def test_hasta_clock_time_in_words_is_not_one_way(cfg, text):
    p = params(text, cfg)
    assert p.loop is True and p.distance_km == 5 and p.duration_min is None


def test_hasta_word_that_is_not_an_hour_is_still_one_way(cfg):
    assert params("5 km hasta la fuente", cfg).loop is False
    assert params("5 km hasta la unidad de salud", cfg).loop is False   # «una» solo como palabra entera


def test_clock_numbers_are_required_in_config(cfg):
    broken = copy.deepcopy(cfg)
    del broken["interpret"]["clock_numbers"]
    with pytest.raises(ValueError, match="clock_numbers"):
        validate_assistant_config(broken)
