import pytest

import schemas as s
import settings
from ai.dictionary import Analysis
from ai.provider import RulesProvider, build_provider

EXAMPLE = "15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado"


class FakeLanguage:
    def __init__(self, analysis=None, error=None):
        self.analysis, self.error, self.texts = analysis, error, []

    def analyze(self, text):
        self.texts.append(text)
        if self.error:
            raise self.error
        return self.analysis


@pytest.fixture(scope="module")
def cfg():
    return settings.load("assistant")


def test_uses_oci_analysis(cfg):
    language = FakeLanguage(Analysis(phrases=["parque"]))
    res = RulesProvider(cfg, language).interpret("ruta de 5 km")
    assert res.params.pass_by == ["park"] and language.texts == ["ruta de 5 km"]


def test_oci_failure_falls_back_to_dictionary(cfg):
    res = RulesProvider(cfg, FakeLanguage(error=RuntimeError("caido"))).interpret(EXAMPLE)
    assert res.params.distance_km == 15 and "fountain" in res.params.pass_by


def test_without_language_uses_recorded_or_dictionary(cfg):
    assert RulesProvider(cfg).interpret(EXAMPLE).params.distance_km == 15
    assert RulesProvider(cfg).interpret("5 km con fuentes").params.pass_by == ["fountain"]


def test_write_up_templates(cfg):
    provider = RulesProvider(cfg)
    conditions = [s.Condition(condition="Pasar por: parque", met=True, detail="Pasa por «Parque Uno»."),
                  s.Condition(condition="Circular", met=False, detail="Todavía no.")]
    assert provider.write_up(conditions, "2,4 km, 30 min a pie") == \
        "2,4 km, 30 min a pie. Cumple 1 de 2 condiciones. No cumple: circular."
    three = conditions + [s.Condition(condition="Evitar: cuestas", met=False, detail="Sin datos.")]
    assert provider.write_up(three, "1 km").endswith("No cumple: circular y evitar: cuestas.")
    assert provider.write_up([], "1 km") == "1 km."
    assert callable(provider.interpret) and callable(provider.write_up)


def test_build_provider_without_credentials(cfg):
    provider = build_provider(cfg, {})
    assert provider.language is None
