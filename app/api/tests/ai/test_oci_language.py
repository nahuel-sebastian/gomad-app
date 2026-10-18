from types import SimpleNamespace as NS

import pytest

import settings
from ai.dictionary import Analysis
from ai.oci_language import OciLanguage, from_env
from ai.recorded import recorded


class FakeClient:
    """Cliente de OCI Language simulado: guarda lo que recibe y nunca abre red."""

    def __init__(self):
        self.calls = []

    def batch_detect_language_entities(self, details):
        self.calls.append(details)
        return NS(data=NS(documents=[NS(entities=[NS(text="15 km", type="QUANTITY", score=0.9)])]))

    def batch_detect_language_key_phrases(self, details):
        self.calls.append(details)
        return NS(data=NS(documents=[NS(key_phrases=[NS(text="parque", score=0.8)])]))


@pytest.fixture(scope="module")
def cfg():
    return settings.load("assistant")


def test_analyze_sends_only_text(cfg):
    client = FakeClient()
    analysis = OciLanguage(client, "ocid1.compartment.test", cfg["oci"]["language_code"]).analyze("15 km por un parque")
    assert analysis == Analysis(entities=[("15 km", "QUANTITY")], phrases=["parque"])
    assert len(client.calls) == 2
    for details in client.calls:
        assert details.compartment_id == "ocid1.compartment.test"
        assert len(details.documents) == 1
        assert details.documents[0].text == "15 km por un parque"
        assert details.documents[0].language_code == "es"


def test_from_env_without_credentials(cfg, tmp_path):
    assert from_env({}, cfg) is None
    assert from_env({"IA_PROVEEDOR": "oci_language", "OCI_COMPARTMENT_ID": "x",
                     "OCI_CONFIG_FILE": str(tmp_path / "no")}, cfg) is None
    assert from_env({"IA_PROVEEDOR": "otro", "OCI_COMPARTMENT_ID": "x"}, cfg) is None
    assert from_env({"IA_PROVEEDOR": "oci_language"}, cfg) is None


def test_from_env_bad_config_file_is_none(cfg, tmp_path):
    bad = tmp_path / "config"
    bad.write_text("esto no es una config de OCI\n")
    assert from_env({"IA_PROVEEDOR": "oci_language", "OCI_COMPARTMENT_ID": "x", "OCI_CONFIG_FILE": str(bad)}, cfg) is None


def test_recorded_by_normalized_text():
    text = "15 KM andando, por un parque, con fuentes y bancos y que pase por un supermercado "
    assert isinstance(recorded(text), Analysis)
    assert recorded("otra cosa") is None


def test_recorded_demo_phrases_interpret_like_the_dictionary(cfg):
    from ai.dictionary import interpret_text
    from ai.recorded import RECORDED

    assert len(RECORDED) == 5
    for text, analysis in RECORDED.items():
        with_oci = interpret_text(text, analysis, cfg)
        assert with_oci.params is not None, text
        assert with_oci == interpret_text(text, None, cfg), text


def test_recorded_dani_is_round_trip(cfg):
    from ai.dictionary import interpret_text

    text = "Media hora con mi hija hasta unos columpios y volver, sin tráfico"
    analysis = recorded(text)
    assert analysis is not None
    p = interpret_text(text, analysis, cfg).params
    assert p.loop is True and p.pass_by == ["playground"] and p.avoid == ["traffic"] and p.duration_min == 30
